"""
智能去重系统 (Ultra-Fast Engine v3)
实现高性能内容相似度检测、LSH Forest 近似查询与墓碑状态管理
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Tuple, Any, Set, List
from collections import OrderedDict
from datetime import datetime

from core.config import settings
from services.dedup import tools
from services.dedup.types import DedupContext, DedupConfig, DedupResult
from services.dedup.strategies import (
    SignatureStrategy,
    VideoStrategy,
    ContentStrategy,
    SimilarityStrategy
)
from core.helpers.tombstone import tombstone

logger = logging.getLogger(__name__)

class SmartDeduplicator:
    """
    智能去重器 (Facade)
    - 编排分布式去重策略
    - 管理 L0 (Bloom), L1 (Memory), L2 (PCache), L3 (LSH), L4 (DB) 级缓存
    - 支持墓碑化 (Tombstone) 自动休眠与唤醒
    """

    def __init__(self):
        # L1 内存缓存: chat_id -> {id: timestamp}
        self.time_window_cache: Dict[str, OrderedDict] = {}
        self.content_hash_cache: Dict[str, OrderedDict] = {}
        self.text_fp_cache: Dict[str, OrderedDict] = {}
        
        # LSH 近似索引 (chat_id -> LSHForest)
        self.lsh_forests: Dict[str, Any] = {}

        # 懒加载组件
        self._repo = None
        self._pcache_repo = None
        self.bloom_filter = None
        self.hll = None
        self.simhash_engine = None
        
        # 写缓冲队列 (Batch Insert)
        self._write_buffer = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task = None

        # 策略链
        self.strategies = [
            SignatureStrategy(),
            VideoStrategy(),
            ContentStrategy(),
            SimilarityStrategy()
        ]

        self._bg_tasks = set()
        self._chat_locks = {}
        self._locks_lock = asyncio.Lock()
        
        # 配置
        self.config = DedupConfig()
        
        # 基础设施初始化
        self._init_infrastructure()
        
        # 注册到墓碑管理器 (黑科技：内存压后台)
        tombstone.register(
            name="smart_dedup",
            get_state_func=self._hibernate_state,
            restore_state_func=self._wakeup_state,
        )

    def _init_infrastructure(self):
        """核心算法组件初始化"""
        try:
            from core.algorithms.bloom_filter import GlobalBloomFilter
            self.bloom_filter = GlobalBloomFilter.get_filter(
                "dedup_l0",
                capacity=getattr(settings, "BLOOM_FILTER_CAPACITY", 2000000),
                error_rate=getattr(settings, "BLOOM_FILTER_ERROR_RATE", 0.0005),
            )
            
            from core.algorithms.hll import GlobalHLL
            self.hll = GlobalHLL.get_hll("dedup_unique_msgs")
            
            from core.algorithms.simhash import SimHash
            self.simhash_engine = SimHash()
            
            logger.info("去重引擎基础设施完成 (Bloom/HLL/SimHash)")
        except Exception as e:
            logger.error(f"基础设施初始化失败: {e}")

    def _get_lsh_forest(self, chat_id: str):
        """按需获取/创建 LSH Forest 索引"""
        if chat_id not in self.lsh_forests:
            try:
                from core.algorithms.lsh_forest import LSHForest
                self.lsh_forests[chat_id] = LSHForest(num_trees=4, prefix_length=64)
            except Exception:
                return None
        return self.lsh_forests[chat_id]

    @property
    def repo(self):
        if not self._repo:
            from repositories.dedup_repo import DedupRepository
            from core.container import container
            self._repo = DedupRepository(container.db)
        return self._repo

    @property
    def pcache_repo(self):
        if not self._pcache_repo:
            from repositories.persistent_cache_repository import PersistentCacheRepository
            self._pcache_repo = PersistentCacheRepository()
        return self._pcache_repo

    def _hibernate_state(self):
        """[Tombstone] 冻结逻辑: 导出内存索引层"""
        state = {
            "time_window_cache": self.time_window_cache,
            "content_hash_cache": self.content_hash_cache,
            "text_fp_cache": self.text_fp_cache,
            "lsh_forests": {
                cid: {"trees": forest.trees, "num_trees": forest.num_trees, "k": forest.prefix_length}
                for cid, forest in self.lsh_forests.items()
            },
        }
        self.time_window_cache = {}
        self.content_hash_cache = {}
        self.text_fp_cache = {}
        self.lsh_forests = {}
        logger.debug("SmartDeduplicator 进入冬眠")
        return state

    def _wakeup_state(self, state):
        """[Tombstone] 复苏逻辑: 恢复内存索引层"""
        if not state: return
        self.time_window_cache = state.get("time_window_cache", {})
        self.content_hash_cache = state.get("content_hash_cache", {})
        self.text_fp_cache = state.get("text_fp_cache", {})
        
        # 恢复 LSH 索引
        forest_data = state.get("lsh_forests", {})
        self.lsh_forests = {}
        for cid, data in forest_data.items():
            try:
                from core.algorithms.lsh_forest import LSHForest
                f = LSHForest(num_trees=data.get("num_trees", 4), prefix_length=data.get("k", 64))
                f.trees = data.get("trees", [])
                self.lsh_forests[cid] = f
            except Exception as e:
                logger.warning(f"从墓碑恢复 LSH 索引失败 ({cid}): {e}")
                
        logger.debug("SmartDeduplicator 已唤醒")

    async def check_duplicate(
        self,
        message_obj,
        target_chat_id: int,
        rule_config: Dict = None,
        *,
        readonly: bool = False,
        skip_media_sig: bool = False,
    ) -> Tuple[bool, str]:
        """门面接口: 执行去重检测"""
        
        # 自动复苏 (墓碑触发)
        if tombstone._is_frozen:
            await tombstone.resurrect()

        async with await self._get_chat_lock(target_chat_id):
            start_ts = time.time()
            
            # 1. 构造 Context
            final_config = self._build_config(rule_config, skip_media_sig, readonly)
            ctx = DedupContext(
                message_obj=message_obj,
                target_chat_id=target_chat_id,
                config=final_config,
                repo=self.repo,
                pcache_repo=self.pcache_repo,
                time_window_cache=self.time_window_cache,
                content_hash_cache=self.content_hash_cache,
                text_fp_cache=self.text_fp_cache,
                lsh_forests=self.lsh_forests,
                bloom_filter=self.bloom_filter,
                hll=self.hll,
                bg_tasks=self._bg_tasks,
                logger=logger,
                simhash_provider=self.simhash_engine
            )

            # 2. 执行策略链
            for strategy in self.strategies:
                res = await strategy.process(ctx)
                if res and res.is_duplicate:
                    logger.debug(f"去重命中 [{res.algo}]: {res.reason}")
                    return True, res.reason

            # 3. 记录消息 (Batched Write)
            if not readonly and final_config.enable_dedup:
                await self._record_message(ctx)

            return False, "无重复"

    async def _get_chat_lock(self, chat_id: int):
        async with self._locks_lock:
            if chat_id not in self._chat_locks:
                self._chat_locks[chat_id] = asyncio.Lock()
            return self._chat_locks[chat_id]

    def _build_config(self, rule_config, skip_media_sig, readonly) -> DedupConfig:
        c = DedupConfig()
        # 合并默认值与传入配置
        base = rule_config or {}
        for k, v in base.items():
            if hasattr(c, k): setattr(c, k, v)
        c.skip_media_sig = skip_media_sig
        c.readonly = readonly
        return c

    def _create_context(self, message_obj, chat_id, config=None) -> DedupContext:
        """内部方法：快速构造上下文"""
        final_config = config or self.config
        return DedupContext(
            message_obj=message_obj,
            target_chat_id=chat_id,
            config=final_config,
            repo=self.repo,
            pcache_repo=self.pcache_repo,
            time_window_cache=self.time_window_cache,
            content_hash_cache=self.content_hash_cache,
            text_fp_cache=self.text_fp_cache,
            lsh_forests=self.lsh_forests,
            bloom_filter=self.bloom_filter,
            hll=self.hll,
            bg_tasks=self._bg_tasks,
            logger=logger,
            simhash_provider=self.simhash_engine
        )

    async def record_message(self, message_obj, chat_id: int, signature: str = None, content_hash: str = None):
        """兼容性接口: 记录消息指纹"""
        ctx = self._create_context(message_obj, chat_id)
        # 如果传入了特定的指纹，强制使用
        await self._record_message(ctx, signature, content_hash)

    # 别名兼容
    _record_message_legacy = record_message

    async def _record_message(self, ctx: DedupContext, force_sig: str = None, force_hash: str = None):
        """记录消息到多级索引和写缓冲队列"""
        try:
            msg = ctx.message_obj
            cid = str(ctx.target_chat_id)
            ts = time.time()
            config = ctx.config

            # 提取指纹
            sig = force_sig or (tools.generate_signature(msg) if not config.skip_media_sig else None)
            chash = force_hash or tools.generate_content_hash(msg)
            
            # 1. 更新 Bloom (L0)
            if self.bloom_filter:
                if sig: self.bloom_filter.add(f"sig:{cid}:{sig}")
                if chash: self.bloom_filter.add(f"hash:{cid}:{chash}")

            # 2. 更新内存 L1 (有序字典滚动淘汰)
            if sig:
                if cid not in self.time_window_cache: self.time_window_cache[cid] = OrderedDict()
                self.time_window_cache[cid][sig] = ts
            
            if chash:
                if cid not in self.content_hash_cache: self.content_hash_cache[cid] = OrderedDict()
                self.content_hash_cache[cid][chash] = ts

            # 3. 文本相似度指纹 (LSH + Pruning Metadata)
            text = getattr(msg, "message", "") or getattr(msg, "text", "")
            if text:
                cleaned = tools.clean_text_for_hash(text, config.get("strip_numbers", True))
                if len(cleaned) >= config.get("min_text_length", 10):
                    fp = tools.calculate_simhash(cleaned)
                    if fp:
                        # 记录 fp 及其元数据 (长度，时间等)
                        if cid not in self.text_fp_cache: self.text_fp_cache[cid] = OrderedDict()
                        self.text_fp_cache[cid][fp] = {"ts": ts, "len": len(cleaned)}
                        
                        # 加入 LSH Forest
                        forest = self._get_lsh_forest(cid)
                        if forest: forest.add(str(ts), fp)

            # 4. 更新 HLL
            if self.hll and hasattr(msg, 'id'):
                self.hll.add(f"{cid}:{msg.id}")

            # 5. 加入数据库写缓冲 (带丰富元数据支持以后续复核)
            doc = getattr(msg, 'video', None) or getattr(msg, 'photo', None) or getattr(msg, 'document', None)
            payload = {
                "chat_id": cid,
                "signature": sig,
                "content_hash": chash,
                "file_id": str(getattr(msg, 'id', '0')),
                "media_type": str(getattr(msg, 'type', 'unknown')),
                "file_size": int(getattr(doc, 'size', 0) or 0) if doc else 0,
                "duration": int(getattr(doc, 'duration', 0) or 0) if doc else 0,
                "width": int(getattr(doc, 'w', 0) or 0) if doc else 0,
                "height": int(getattr(doc, 'h', 0) or 0) if doc else 0,
                "count": 1,
                "created_at": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }
            async with self._buffer_lock:
                self._write_buffer.append(payload)
                if len(self._write_buffer) > 100:
                    await self._flush_buffer()
            
            # 6. 内存 L1 滚动淘汰 (防止 OOM)
            max_sig_size = config.get("max_signature_cache_size", 5000)
            if len(self.time_window_cache[cid]) > max_sig_size:
                self.time_window_cache[cid].popitem(last=False)
                
            max_hash_size = config.get("max_content_hash_cache_size", 2000)
            if len(self.content_hash_cache[cid]) > max_hash_size:
                self.content_hash_cache[cid].popitem(last=False)

            # 确保后台刷写任务启动
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._buffer_flush_worker())

        except Exception as e:
            logger.warning(f"记录消息指纹失败: {e}")

    async def remove_message(
        self, 
        message_obj,
        chat_id: int,
        signature: Optional[str] = None, 
        content_hash: Optional[str] = None
    ):
        """从缓存和数据库中移除消息 (回滚逻辑)"""
        try:
            target_chat_id = chat_id
            config = self.config

            # 1. 生成指纹 (如果缺失)
            if not signature:
                signature = tools.generate_signature(message_obj) if not config.skip_media_sig else None
            if not content_hash:
                content_hash = tools.generate_content_hash(message_obj)
            
            # 2. 从 Repo 移除
            if signature:
                await self.repo.delete_media_signature(target_chat_id, signature)
            if content_hash:
                await self.repo.delete_content_hash(target_chat_id, content_hash)
                
            # 3. 从内存缓存移除
            cid = str(target_chat_id)
            if signature and cid in self.time_window_cache:
                self.time_window_cache[cid].pop(signature, None)
            if content_hash and cid in self.content_hash_cache:
                self.content_hash_cache[cid].pop(content_hash, None)
            
            # 4. 从写缓冲移除 (防止尚未刷入 DB 的记录生效)
            async with self._buffer_lock:
                 self._write_buffer = [
                     item for item in self._write_buffer 
                     if not (item.get('chat_id') == cid and 
                             (item.get('signature') == signature or item.get('content_hash') == content_hash))
                 ]
                
            logger.debug(f"已回退会话 {target_chat_id} 的去重状态")
        except Exception as e:
            logger.warning(f"移除消息失败: {e}")

    async def _buffer_flush_worker(self):
        """后台低频刷写任务"""
        while True:
            await asyncio.sleep(5.0)
            await self._flush_buffer()

    async def _flush_buffer(self):
        async with self._buffer_lock:
            if not self._write_buffer: return
            batch = self._write_buffer[:]
            self._write_buffer.clear()
        
        if self.repo:
            await self.repo.batch_add_media_signatures(batch)

    async def update_config(self, new_config: Dict):
        for k, v in new_config.items():
            if hasattr(self.config, k): setattr(self.config, k, v)
        try: await self.repo.save_config(new_config)
        except: pass

    def get_stats(self) -> Dict:
        return {
            "cached_signatures": sum(len(c) for c in self.time_window_cache.values()),
            "cached_content_hashes": sum(len(c) for c in self.content_hash_cache.values()),
            "lsh_forests": len(self.lsh_forests),
            "tracked_chats": len(self.time_window_cache),
            "buffer_size": len(self._write_buffer)
        }

    async def reset_to_defaults(self):
        self.config = DedupConfig()

# 全局实例
smart_deduplicator = SmartDeduplicator()
