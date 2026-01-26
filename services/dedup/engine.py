"""
智能去重系统
实现内容相似度检测和时间窗口去重
"""

import hashlib
from collections import OrderedDict
from difflib import SequenceMatcher

import asyncio
import logging
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Any

from core.helpers.tombstone import tombstone

try:
    # 可选快速文本相似度库（更快更准）
    from rapidfuzz import fuzz  # type: ignore

    _HAS_RAPIDFUZZ = True
except Exception:
    _HAS_RAPIDFUZZ = False

try:
    import xxhash

    _HAS_XXHASH = True
except ImportError:
    _HAS_XXHASH = False

try:
    from numba import jit

    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False

    # 定义一个空装饰器作为回退
    def jit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


logger = logging.getLogger(__name__)


# Numba 优化的汉明距离计算
@jit(nopython=True, cache=True)
def _fast_hamming_64(a: int, b: int) -> int:
    # Numba 会将其编译为极其高效的机器码
    x = (a ^ b) & 0xFFFFFFFFFFFFFFFF
    # Kernighan 算法在 JIT 下比 bit_count 更通用且极快
    c = 0
    while x:
        x &= x - 1
        c += 1
    return c


class SmartDeduplicator:
    """智能去重器"""

    def __init__(self):
        # 时间窗口缓存 (chat_id -> {signature: timestamp})
        self.time_window_cache = {}
        # 内容哈希缓存 (chat_id -> {content_hash: timestamp})
        self.content_hash_cache = {}
        # 文本缓存 (chat_id -> [ {'text': cleaned_text, 'ts': timestamp}, ... ])
        self.text_cache = {}
        # 文本指纹缓存（SimHash 64bit）：(chat_id -> [ {'fp': int, 'ts': timestamp}, ... ])
        self.text_fp_cache = {}
        # 写缓冲队列：用于批量写入数据库
        self._write_buffer = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task = None  # 后台刷写任务
        self._bg_tasks = set()   # 后台计算任务集合
        # 默认配置
        self.config = {
            "enable_time_window": True,
            "time_window_hours": 24,
            "similarity_threshold": 0.85,
            "enable_content_hash": True,
            "enable_smart_similarity": True,
            "cache_cleanup_interval": 3600,  # 1小时清理一次
            "enable_persistent_cache": True,  # 使用持久化缓存跨重启保留窗口命中
            "persistent_cache_ttl_seconds": int(
                os.getenv("DEDUP_PERSIST_TTL_SECONDS", "2592000")
            ),  # 30天上限
            # 新增配置项
            "max_text_cache_size": 300,  # 每个会话最多缓存多少条文本用于相似度检查
            "min_text_length": 10,  # 触发相似度检查的最小清洗后文本长度
            "strip_numbers": True,  # 清洗文本时是否移除数字
            # 文本相似度预筛（固定长度指纹/SimHash，用于快速过滤）
            "enable_text_fingerprint": True,
            "fingerprint_ngram": 3,  # 词级 n-gram 大小
            "fingerprint_hamming_threshold": 3,  # 汉明距离阈值（0 为完全一致）
            "max_text_fp_cache_size": 500,  # 每个会话最多缓存的文本指纹条数
            "max_similarity_checks": 50,  # 最多做多少次精确相似度比较
            # 文本相似度在含视频消息中的应用（默认关闭，避免不同视频同标题被误杀）
            "enable_text_similarity_for_video": False,
            # 视频专用
            "enable_video_file_id_check": True,  # 基于 telegram file id 的快速判重
            "enable_video_partial_hash_check": True,  # 基于视频部分字节哈希的判重
            "video_partial_hash_bytes": 262144,  # 每段读取的字节数（默认256KB）
            "video_partial_hash_on_fileid_miss_only": True,  # 仅在 file_id 未命中重复时再计算部分哈希
            "video_partial_hash_min_size_bytes": 5
            * 1024
            * 1024,  # 小视频不做部分哈希（默认>=5MB）
            # 视频哈希持久化缓存（避免重复下载/重复计算）
            "video_hash_persist_ttl_seconds": int(
                os.getenv("VIDEO_HASH_PERSIST_TTL_SECONDS", "15552000")
            ),  # 180天
            # 视频严格复核：哈希命中后对时长/分辨率/大小范围做阈值校验
            "video_strict_verify": True,
            "video_duration_tolerance_sec": 2,
            "video_resolution_tolerance_px": 8,
            "video_size_bucket_tolerance": 1,
        }
        self.last_cleanup = time.time()
        # 配置加载标记：使用懒加载模式，避免在模块初始化阶段执行数据库操作
        self._config_loaded = False

        # 预编译正则表达式
        # 基础文本清洗正则：匹配 URL、@提及、#标签
        self._re_basic_clean = re.compile(r"http[s]?://\S+|@\w+|#\w+", re.I)
        # 用于 URL/Mention 去除的简单正则
        self._re_complex_patterns = re.compile(r"http\S+|@\w+|#\w+", re.I)
        # 使用str.translate的转换表，预计算以提高性能
        import string

        # 定义要删除的字符：标点符号 + 不可见字符
        self.trans_table_keep_nums = str.maketrans("", "")
        self.trans_table_no_nums = str.maketrans("", "")

        # 汉明距离转换表已预计算
        self.trans_table_keep_nums = str.maketrans({c: None for c in string.punctuation + "\n\r\t"})
        self.trans_table_no_nums = str.maketrans({c: None for c in string.punctuation + string.digits + "\n\r\t"})

        # 初始化 Bloom Filter (L0 缓存)
        try:
            from utils.processing.bloom_filter import GlobalBloomFilter
            self.bloom_filter = GlobalBloomFilter.get_filter("smart_dedup")
            logger.info("Bloom Filter (L0) 初始化成功")
        except Exception as e:
            logger.error(f"Bloom Filter 初始化失败: {e}")
            self.bloom_filter = None

        # 初始化 HLL (HyperLogLog) 用于基数统计
        try:
            from utils.processing.hll import GlobalHLL
            self.hll = GlobalHLL.get_hll("unique_messages_today")
            logger.info("HLL (HyperLogLog) 初始化成功")
        except Exception as e:
            logger.error(f"HLL 初始化失败: {e}")
            self.hll = None

        # 初始化 LSH Forest (用于语义去重)
        try:
            from utils.processing.simhash import SimHash
            from utils.algorithm.lsh_forest import LSHForest
            self.simhash_engine = SimHash()
            # 初始化索引 (chat_id -> LSHForest)
            self.lsh_forests = {}
            logger.info("SimHash 引擎与 LSH Forest 索引系统初始化成功")
        except Exception as e:
            logger.error(f"LSH Forest 初始化失败: {e}")
            self.simhash_engine = None
            self.lsh_forests = {}

        # ✅ 注册到墓碑管理器
        tombstone.register(
            name="smart_dedup",
            get_state_func=self._hibernate_state,
            restore_state_func=self._wakeup_state,
        )

    @property
    def repo(self):
        from core.container import container
        return container.dedup_repo

    # --- 新增：休眠逻辑 (导出数据并清空自己) ---
    def _hibernate_state(self):
        """导出状态并清空内存"""
        state = {
            "time_window": self.time_window_cache,
            "content_hash": self.content_hash_cache,
            "text": self.text_cache,
            "text_fp": self.text_fp_cache,
            "lsh_forests": self.lsh_forests,
        }
        # 🚨 关键：彻底清空内存中的字典
        self.time_window_cache = {}
        self.content_hash_cache = {}
        self.text_cache = {}
        self.text_fp_cache = {}
        self.lsh_forests = {}
        return state

    # --- 新增：唤醒逻辑 (恢复数据) ---
    def _wakeup_state(self, state):
        """恢复状态"""
        if not state:
            return
        self.time_window_cache = state.get("time_window", {})
        self.content_hash_cache = state.get("content_hash", {})
        self.text_cache = state.get("text", {})
        self.text_fp_cache = state.get("text_fp", {})
        self.lsh_forests = state.get("lsh_forests", {})

    async def _lazy_load_config(self):
        """懒加载配置：在第一次使用时从数据库加载配置"""
        if self._config_loaded:
            return
        logger.debug("开始懒加载去重配置...")
        try:
            await asyncio.to_thread(self._load_config_from_db)
            self._config_loaded = True
            logger.debug("懒加载配置完成")
        except Exception as e:
            logger.warning(f"懒加载配置失败: {e}，将使用默认配置继续运行")
            self._config_loaded = True  # 避免重复尝试加载

    async def _compute_and_save_video_hash_bg(self, message_obj, partial_bytes, file_id, target_chat_id, config):
        """后台计算视频哈希并保存到DB/Cache"""
        try:
            logger.info(f"后台开始计算视频哈希: {file_id}")
            vhash = await self._compute_video_partial_hash(message_obj, partial_bytes)
            if vhash:
                logger.info(f"后台哈希计算完成: {file_id} -> {vhash}")
                
                # 1. 写入持久化缓存
                try:
                    ttl = int(config.get("video_hash_persist_ttl_seconds", 15552000))
                    await self._write_video_hash_pcache(str(file_id), vhash, ttl)
                except Exception as e:
                    logger.error(f"后台写入PCache失败: {e}")

                # 2. 写入数据库
                # 使用特殊的 signature "video_hash:{hash}" 以避免与主流程的 "video:{file_id}" 冲突
                try:
                    await self._record_message(
                        message_obj, 
                        target_chat_id, 
                        signature=f"video_hash:{vhash}", 
                        content_hash=vhash
                    )
                    logger.debug(f"后台哈希记录已存入DB缓冲: {vhash}")
                except Exception as e:
                    logger.error(f"后台写入DB失败: {e}")
            else:
                logger.warning(f"后台计算哈希返回空: {file_id}")
        except Exception as e:
            logger.error(f"后台视频处理任务异常: {e}", exc_info=True)

    async def check_duplicate(
        self,
        message_obj,
        target_chat_id: int,
        rule_config: Dict = None,
        *,
        readonly: bool = False,
    ) -> Tuple[bool, str]:
        """
        检查消息是否为重复
        返回: (is_duplicate, reason)
        """
        start_ts = time.time()
        logger.debug(
            f"开始去重检查，目标chat_id: {target_chat_id}, 消息类型: {type(message_obj).__name__}"
        )
        try:
            # ✅ 关键：每次使用前检查是否处于冷冻状态
            # 如果已冻结，先复苏 (Lazy Loading)
            logger.debug("检查冷冻状态...")
            if tombstone._is_frozen:
                logger.debug("检测到冷冻状态，尝试复苏...")
                try:
                    await tombstone.resurrect()
                    logger.debug("复苏成功")
                except Exception as e:
                    logger.error(f"自动复苏失败: {e}，将使用空缓存继续运行")
                    # 强制解除冻结状态，避免死循环
                    tombstone._is_frozen = False
                    # 这里不需要做额外操作，因为 _wakeup_state 没被调用的话
                    # 缓存就是空的，程序会正常运行（只是暂时无法去重旧消息）

            # 懒加载配置
            await self._lazy_load_config()

            # 定期清理缓存
            logger.debug("检查是否需要清理缓存...")
            await self._cleanup_cache_if_needed()
            logger.debug("缓存清理检查完成")

            # 合并配置
            config = {**self.config, **(rule_config or {})}
            logger.debug(f"使用配置: {config}")

            # 1. 传统签名去重
            logger.debug("开始生成消息签名...")
            signature = self._generate_signature(message_obj)
            logger.debug(f"生成签名: {signature}")
            if signature:
                # L0: Bloom Filter 预判
                if self.bloom_filter:
                    bloom_key = f"sig:{target_chat_id}:{signature}"
                    if bloom_key not in self.bloom_filter:
                        # 100% 确定不重复，直接跳过后续昂贵的 DB/PCache 检查
                        logger.debug(f"Bloom Filter (L0) 确认签名不重复: {signature}")
                        # 仅记录到 Bloom Filter (实际记录到 DB 会在流程结束时调用 _record_message)
                        # 这里我们返回 False，进入后续流程
                        pass
                    else:
                        logger.debug(f"Bloom Filter (L0) 命中，可能重复: {signature}")
                
                # 先查持久化缓存（跨重启热命中），命中即返回
                if await self._check_pcache_hit("sig", target_chat_id, signature):
                    logger.debug(f"持久化缓存签名命中: {signature}")
                    try:
                        from core.helpers.metrics import (
                            DEDUP_DECISIONS_TOTAL,
                            DEDUP_HITS_TOTAL,
                        )

                        DEDUP_HITS_TOTAL.labels(method="signature_pcache").inc()
                        DEDUP_DECISIONS_TOTAL.labels(
                            result="duplicate", method="signature_pcache"
                        ).inc()
                    except Exception as e:
                        logger.debug(f"Metrics record failed: {e}")
                        pass
                    return True, "签名重复: persistent cache 命中"
                logger.debug(f"检查签名重复: {signature}")
                is_dup, reason = await self._check_signature_duplicate(
                    signature, target_chat_id, config
                )
                if is_dup:
                    logger.debug(f"签名重复命中: {reason}")
                    try:
                        from core.helpers.metrics import (
                            DEDUP_DECISIONS_TOTAL,
                            DEDUP_HITS_TOTAL,
                        )

                        DEDUP_HITS_TOTAL.labels(method="signature").inc()
                        DEDUP_DECISIONS_TOTAL.labels(
                            result="duplicate", method="signature"
                        ).inc()
                        from core.helpers.metrics import DEDUP_CHECK_SECONDS

                        DEDUP_CHECK_SECONDS.observe(max(0.0, time.time() - start_ts))
                    except Exception as e:
                        logger.debug(f"Metrics record failed: {e}")
                        pass
                    return True, f"签名重复: {reason}"

            # 2. 视频优先判重（将视频相关检查提前，避免被内容哈希/文本相似度误杀）
            logger.debug("检查是否为视频消息...")
            is_video = self._is_video(message_obj)
            logger.debug(f"视频消息检查结果: {is_video}")

            if is_video:
                # file_id 判重
                logger.debug("开始视频file_id判重...")
                file_id_checked = False
                file_id_found_duplicate = False
                if config.get("enable_video_file_id_check", True):
                    try:
                        file_id = self._extract_video_file_id(message_obj)
                        logger.debug(f"提取到视频file_id: {file_id}")
                        if file_id:
                            file_id_checked = True
                            is_dup = await self._check_video_duplicate_by_file_id(
                                file_id, target_chat_id
                            )
                            logger.debug(f"视频file_id重复检查结果: {is_dup}")
                            if is_dup:
                                file_id_found_duplicate = True
                                try:
                                    from core.helpers.metrics import (
                                        DEDUP_DECISIONS_TOTAL,
                                        DEDUP_HITS_TOTAL,
                                    )

                                    DEDUP_HITS_TOTAL.labels(
                                        method="video_file_id"
                                    ).inc()
                                    DEDUP_DECISIONS_TOTAL.labels(
                                        result="duplicate", method="video_file_id"
                                    ).inc()
                                    from core.helpers.metrics import DEDUP_CHECK_SECONDS

                                    DEDUP_CHECK_SECONDS.observe(
                                        max(0.0, time.time() - start_ts)
                                    )
                                except Exception:
                                    pass
                                return True, "视频file_id重复"
                            try:
                                setattr(message_obj, "_tf_file_id", str(file_id))
                            except Exception:
                                pass
                    except Exception as _ve:
                        logger.debug(f"视频 file_id 判重失败: {_ve}")
                # 部分哈希判重（可选：仅在 file_id 未命中重复时执行；可配置最小文件大小阈值）
                logger.debug("开始视频部分哈希判重...")
                if config.get("enable_video_partial_hash_check", True):
                    only_on_miss = bool(
                        config.get("video_partial_hash_on_fileid_miss_only", True)
                    )
                    # 逻辑：如果不是"仅错过时"模式，总是运行；如果是"仅错过时"模式，只在file_id检查了但没找到重复时运行
                    should_run = (not only_on_miss) or (
                        only_on_miss and file_id_checked and not file_id_found_duplicate
                    )
                    logger.debug(
                        f"视频部分哈希判重条件: should_run={should_run}, only_on_miss={only_on_miss}, file_id_checked={file_id_checked}, file_id_found_duplicate={file_id_found_duplicate}"
                    )
                    if should_run:
                        try:
                            min_size = int(
                                config.get(
                                    "video_partial_hash_min_size_bytes", 5 * 1024 * 1024
                                )
                            )
                            # 若可获取文件大小，做阈值过滤
                            doc = getattr(message_obj, "document", None)
                            if doc is None and hasattr(message_obj, "video"):
                                doc = getattr(message_obj, "video")
                            size_ok = True
                            if doc is not None:
                                try:
                                    size_val = int(getattr(doc, "size", 0) or 0)
                                    if size_val and size_val < min_size:
                                        size_ok = False
                                    logger.debug(
                                        f"视频大小检查: size_val={size_val}, min_size={min_size}, size_ok={size_ok}"
                                    )
                                except Exception:
                                    size_ok = True
                            if size_ok:
                                partial_bytes = int(
                                    config.get("video_partial_hash_bytes", 262144)
                                )
                                # 先查持久化缓存（以 file_id 为键）
                                vhash = None
                                try:
                                    file_id_for_hash = getattr(
                                        getattr(message_obj, "video", None), "id", None
                                    ) or getattr(
                                        getattr(message_obj, "document", None),
                                        "id",
                                        None,
                                    )
                                    if file_id_for_hash:
                                        logger.debug(
                                            f"检查视频哈希持久化缓存: file_id={file_id_for_hash}"
                                        )
                                        vhash = await self._check_video_hash_pcache(
                                            str(file_id_for_hash)
                                        )
                                        logger.debug(f"视频哈希持久化缓存结果: {vhash}")
                                        if vhash:
                                            try:
                                                from core.helpers.metrics import (
                                                    VIDEO_HASH_PCACHE_HITS_TOTAL,
                                                )

                                                VIDEO_HASH_PCACHE_HITS_TOTAL.labels(
                                                    algo="partial_md5"
                                                ).inc()
                                            except Exception:
                                                pass
                                except Exception:
                                    pass

                                if not vhash:
                                    # [Optimization] 异步计算视频哈希，避免阻塞转发流程
                                    # 首次见到的视频（且PCache未命中），放行并后台记录
                                    logger.info(f"视频FileID未命中且无Hash缓存，启动后台计算任务并放行: {file_id_for_hash}")
                                    
                                    task = asyncio.create_task(
                                        self._compute_and_save_video_hash_bg(
                                            message_obj, partial_bytes, file_id_for_hash, target_chat_id, config
                                        )
                                    )
                                    self._bg_tasks.add(task)
                                    task.add_done_callback(self._bg_tasks.discard)
                                    
                                    # 返回 False (不重复) 并不等待哈希结果
                                    return False, "新视频(异步记录)"
                                if vhash:
                                    logger.debug(f"检查视频哈希重复: {vhash}")
                                    is_dup = await self._check_video_duplicate_by_hash(
                                        vhash, target_chat_id
                                    )
                                    logger.debug(f"视频哈希重复检查结果: {is_dup}")
                                    if is_dup:
                                        try:
                                            from core.helpers.metrics import (
                                                DEDUP_DECISIONS_TOTAL,
                                                DEDUP_HITS_TOTAL,
                                            )

                                            DEDUP_HITS_TOTAL.labels(
                                                method="video_partial_hash"
                                            ).inc()
                                            DEDUP_DECISIONS_TOTAL.labels(
                                                result="duplicate",
                                                method="video_partial_hash",
                                            ).inc()
                                            from core.helpers.metrics import (
                                                DEDUP_CHECK_SECONDS,
                                            )

                                            DEDUP_CHECK_SECONDS.observe(
                                                max(0.0, time.time() - start_ts)
                                            )
                                        except Exception:
                                            pass
                                        # 严格复核
                                        try:
                                            if config.get("video_strict_verify", True):
                                                logger.debug("开始视频特征严格复核...")
                                                strict_ok = await self._strict_verify_video_features(
                                                    target_chat_id,
                                                    message_obj,
                                                    file_id_for_hash,
                                                    vhash,
                                                    config,
                                                )
                                                logger.debug(
                                                    f"视频特征严格复核结果: {strict_ok}"
                                                )
                                                if not strict_ok:
                                                    return (
                                                        False,
                                                        "视频特征不一致，忽略哈希命中",
                                                    )
                                        except Exception:
                                            pass
                                        return True, "视频内容哈希重复"
                                    try:
                                        setattr(message_obj, "_tf_content_hash", vhash)
                                    except Exception:
                                        pass
                        except Exception as _ve:
                            logger.debug(f"视频部分哈希判重失败: {_ve}")

            # 3. 内容哈希去重（对视频默认关闭，以避免误杀；可通过配置开启）
            logger.debug("开始内容哈希去重...")
            content_hash = None
            if config.get("enable_content_hash") and (
                not is_video or config.get("enable_content_hash_for_video", False)
            ):
                content_hash = self._generate_content_hash(message_obj)
                logger.debug(f"生成内容哈希: {content_hash}")
                if content_hash:
                    # 先查持久化缓存
                    logger.debug(f"检查持久化缓存内容哈希: {content_hash}")
                    if await self._check_pcache_hit(
                        "hash", target_chat_id, content_hash
                    ):
                        logger.debug(f"持久化缓存内容哈希命中: {content_hash}")
                        try:
                            from core.helpers.metrics import (
                                DEDUP_DECISIONS_TOTAL,
                                DEDUP_HITS_TOTAL,
                            )

                            DEDUP_HITS_TOTAL.labels(method="content_hash_pcache").inc()
                            DEDUP_DECISIONS_TOTAL.labels(
                                result="duplicate", method="content_hash_pcache"
                            ).inc()
                        except Exception:
                            pass
                        return True, "内容重复: persistent cache 命中"
                    logger.debug(f"检查内容哈希重复: {content_hash}")
                    is_dup, reason = await self._check_content_hash_duplicate(
                        content_hash, target_chat_id, config
                    )
                    if is_dup:
                        logger.debug(f"内容哈希重复命中: {reason}")
                        try:
                            from core.helpers.metrics import (
                                DEDUP_DECISIONS_TOTAL,
                                DEDUP_HITS_TOTAL,
                            )

                            DEDUP_HITS_TOTAL.labels(method="content_hash").inc()
                            DEDUP_DECISIONS_TOTAL.labels(
                                result="duplicate", method="content_hash"
                            ).inc()
                            from core.helpers.metrics import DEDUP_CHECK_SECONDS

                            DEDUP_CHECK_SECONDS.observe(
                                max(0.0, time.time() - start_ts)
                            )
                        except Exception:
                            pass
                        return True, f"内容重复: {reason}"

            # 4. 智能相似度（视频或相册默认跳过）
            logger.debug("开始智能相似度检查...")
            if config.get("enable_smart_similarity"):
                # 视频默认跳过文本相似度
                if not (
                    is_video
                    and not config.get("enable_text_similarity_for_video", False)
                ):
                    # 相册/组消息默认跳过
                    if not (
                        getattr(message_obj, "grouped_id", None)
                        and config.get("disable_similarity_for_grouped", True)
                    ):
                        logger.debug("执行相似度检查...")
                        is_dup, reason = await self._check_similarity_duplicate(
                            message_obj, target_chat_id, config
                        )
                        logger.debug(f"相似度检查结果: {is_dup}, {reason}")
                        if is_dup:
                            try:
                                from core.helpers.metrics import (
                                    DEDUP_DECISIONS_TOTAL,
                                    DEDUP_HITS_TOTAL,
                                )

                                DEDUP_HITS_TOTAL.labels(method="similarity").inc()
                                DEDUP_DECISIONS_TOTAL.labels(
                                    result="duplicate", method="similarity"
                                ).inc()
                                from core.helpers.metrics import DEDUP_CHECK_SECONDS

                                DEDUP_CHECK_SECONDS.observe(
                                    max(0.0, time.time() - start_ts)
                                )
                            except Exception:
                                pass
                            return True, f"相似重复: {reason}"

            # 如果检查通过，记录到缓存（只读模式不记录）
            if not readonly:
                logger.debug("记录消息到缓存...")
                await self._record_message(
                    message_obj, target_chat_id, signature, content_hash
                )
                # 记录到 HLL (统计独立消息)
                if self.hll:
                    msg_id = getattr(message_obj, "id", None)
                    chat_id = getattr(message_obj, "chat_id", None)
                    if msg_id and chat_id:
                        self.hll.add(f"{chat_id}:{msg_id}")

                # 同时记录到 Bloom Filter
                # 同时记录到 Bloom Filter
                if self.bloom_filter:
                    if signature: self.bloom_filter.add(f"sig:{target_chat_id}:{signature}")
                    if content_hash: self.bloom_filter.add(f"hash:{target_chat_id}:{content_hash}")

            try:
                from core.helpers.metrics import DEDUP_DECISIONS_TOTAL

                DEDUP_DECISIONS_TOTAL.labels(result="unique", method="final").inc()
                from core.helpers.metrics import DEDUP_CHECK_SECONDS

                DEDUP_CHECK_SECONDS.observe(max(0.0, time.time() - start_ts))
            except Exception:
                pass
            logger.debug(
                f"去重检查完成，耗时: {time.time() - start_ts:.3f}s，结果: 不重复"
            )
            return False, "无重复"

        except Exception as e:
            logger.error(f"智能去重检查失败: {e}")
            try:
                from core.helpers.metrics import DEDUP_CHECK_SECONDS, DEDUP_DECISIONS_TOTAL

                DEDUP_DECISIONS_TOTAL.labels(result="error", method="final").inc()
                DEDUP_CHECK_SECONDS.observe(max(0.0, time.time() - start_ts))
            except Exception:
                pass
            return False, f"检查失败: {e}"

    def _generate_signature(self, message_obj) -> Optional[str]:
        """生成消息签名（与现有系统兼容）"""
        try:
            if hasattr(message_obj, "photo") and message_obj.photo:
                # 照片签名
                photo = message_obj.photo
                if hasattr(photo, "sizes") and photo.sizes:
                    largest = max(photo.sizes, key=lambda x: getattr(x, "size", 0))
                    w = getattr(largest, "w", 0)
                    h = getattr(largest, "h", 0)
                    size = getattr(largest, "size", 0)
                    return f"photo:{w}x{h}:{size}"

            elif hasattr(message_obj, "document") and message_obj.document:
                # 文档签名
                doc = message_obj.document
                doc_id = getattr(doc, "id", "")
                size = getattr(doc, "size", 0)
                mime_type = getattr(doc, "mime_type", "")
                return f"document:{doc_id}:{size}:{mime_type}"

            elif hasattr(message_obj, "video") and message_obj.video:
                # 视频签名
                video = message_obj.video
                # 优先使用 telegram file id（若可用），否则回退到原有规则
                file_id = getattr(video, "id", "") or getattr(
                    video, "file_reference", ""
                )
                duration = getattr(video, "duration", 0)
                return f"video:{file_id or video}:{duration}"

            # 某些客户端将视频暴露在 document 中，这里兜底
            elif (
                hasattr(message_obj, "document")
                and message_obj.document
                and str(getattr(message_obj.document, "mime_type", "")).startswith(
                    "video/"
                )
            ):
                file_id = getattr(message_obj.document, "id", "") or getattr(
                    message_obj.document, "file_reference", ""
                )
                duration = int(
                    getattr(getattr(message_obj, "video", None), "duration", 0) or 0
                )
                return f"video:{file_id}:{duration}"

            return None

        except Exception as e:
            logger.debug(f"生成签名失败: {e}")
            return None

    def _generate_content_hash(self, message_obj) -> Optional[str]:
        """生成内容哈希"""
        try:
            content_parts = []

            # 文本内容
            if hasattr(message_obj, "message") and message_obj.message:
                # 清理文本（移除格式、链接、提及等）
                text = message_obj.message
                cleaned_text = self._clean_text_for_hash(
                    text, strip_numbers=self.config.get("strip_numbers", True)
                )
                if cleaned_text:
                    content_parts.append(f"text:{cleaned_text}")

            # 媒体特征
            if hasattr(message_obj, "media") and message_obj.media:
                media_info = self._extract_media_features(message_obj.media)
                if media_info:
                    content_parts.append(f"media:{media_info}")

            if content_parts:
                combined = "|".join(content_parts)
                return hashlib.md5(combined.encode()).hexdigest()

            return None

        except Exception as e:
            logger.debug(f"生成内容哈希失败: {e}")
            return None

    def _clean_text_for_hash(self, text: str, strip_numbers: bool = False) -> str:
        """清理文本用于哈希计算"""
        if not text:
            return ""

        # 1. 先用正则快速剔除复杂的语义块 (URL, Mention)
        text = self._re_complex_patterns.sub(" ", text.lower())

        # 2. 使用 C 语言层面的 translate 一次性剔除所有标点/数字
        table = (
            self.trans_table_no_nums if strip_numbers else self.trans_table_keep_nums
        )
        text = text.translate(table)

        # 3. 合并空格 (split + join 是最快的标准化空格方法)
        return " ".join(text.split())

    def _is_video(self, message_obj) -> bool:
        """判断消息是否含视频（原生视频或视频文档）。"""
        try:
            if hasattr(message_obj, "video") and getattr(message_obj, "video"):
                return True
            if hasattr(message_obj, "document") and getattr(message_obj, "document"):
                mime = str(
                    getattr(getattr(message_obj, "document"), "mime_type", "") or ""
                )
                return mime.startswith("video/")
        except Exception:
            return False
        return False

    def _extract_video_file_id(self, message_obj) -> Optional[str]:
        """从视频消息中提取文件ID用于去重复检查"""
        try:
            # 检查原生视频
            if hasattr(message_obj, "video") and getattr(message_obj, "video"):
                video = message_obj.video
                file_id = getattr(video, "id", None) or getattr(
                    video, "file_reference", None
                )
                if file_id:
                    return str(file_id)

            # 检查视频文档
            if hasattr(message_obj, "document") and getattr(message_obj, "document"):
                doc = message_obj.document
                mime = str(getattr(doc, "mime_type", "") or "")
                if mime.startswith("video/"):
                    file_id = getattr(doc, "id", None) or getattr(
                        doc, "file_reference", None
                    )
                    if file_id:
                        return str(file_id)

            return None

        except Exception as e:
            logger.debug(f"提取视频文件ID失败: {e}")
            return None

    def _extract_media_features(self, media) -> Optional[str]:
        """提取媒体特征"""
        try:
            features = []

            if hasattr(media, "photo"):
                features.append("type:photo")
                photo = media.photo
                if hasattr(photo, "sizes") and photo.sizes:
                    # 使用尺寸特征而非ID
                    largest = max(photo.sizes, key=lambda x: getattr(x, "size", 0))
                    w = getattr(largest, "w", 0)
                    h = getattr(largest, "h", 0)
                    features.append(f"size:{w}x{h}")

            elif hasattr(media, "document"):
                doc = media.document
                features.append("type:document")

                # 文件大小
                if hasattr(doc, "size"):
                    # 使用大小范围而非精确值
                    size_range = self._get_size_range(doc.size)
                    features.append(f"size_range:{size_range}")

                # MIME类型
                if hasattr(doc, "mime_type"):
                    features.append(f"mime:{doc.mime_type}")

                # 文件名模式（移除数字、日期等变化部分）
                if hasattr(doc, "file_name") and doc.file_name:
                    name_pattern = self._extract_name_pattern(doc.file_name)
                    if name_pattern:
                        features.append(f"pattern:{name_pattern}")

                # 若为视频文档，加入更稳定的维度
                try:
                    if getattr(doc, "mime_type", "").startswith("video/"):
                        duration = getattr(
                            getattr(media, "video", None), "duration", None
                        )
                        if duration:
                            features.append(f"duration:{int(duration)}")
                except Exception:
                    pass

            return "|".join(features) if features else None

        except Exception as e:
            logger.debug(f"提取媒体特征失败: {e}")
            return None

    def _get_size_range(self, size: int) -> str:
        """获取文件大小范围"""
        if size < 1024:
            return "tiny"
        elif size < 1024 * 1024:
            return "small"
        elif size < 10 * 1024 * 1024:
            return "medium"
        elif size < 100 * 1024 * 1024:
            return "large"
        else:
            return "huge"

    def _size_bucket_index(self, bucket: str) -> int:
        order = ["tiny", "small", "medium", "large", "huge"]
        try:
            return order.index(bucket)
        except Exception:
            return -1

    def _extract_name_pattern(self, filename: str) -> str:
        """提取文件名模式"""
        # 移除日期时间
        pattern = re.sub(r"\d{4}[-_]\d{2}[-_]\d{2}", "DATE", filename)
        pattern = re.sub(r"\d{2}[-_:]\d{2}[-_:]\d{2}", "TIME", pattern)

        # 移除数字序列
        pattern = re.sub(r"\d{3,}", "NUM", pattern)

        # 保留扩展名
        if "." in pattern:
            name, ext = pattern.rsplit(".", 1)
            pattern = re.sub(r"[^\w\.]", "_", name) + "." + ext

        return pattern.lower()

    async def _check_signature_duplicate(
        self, signature: str, target_chat_id: int, config: Dict
    ) -> Tuple[bool, str]:
        """检查签名重复"""
        try:
            # 时间窗口检查
            if config.get("enable_time_window"):
                cache_key = str(target_chat_id)
                if cache_key in self.time_window_cache:
                    if signature in self.time_window_cache[cache_key]:
                        last_seen = self.time_window_cache[cache_key][signature]
                        window_hours = config.get("time_window_hours", 24)
                        # 永久窗口：<=0 视为永久
                        if (
                            window_hours <= 0
                            or time.time() - last_seen < window_hours * 3600
                        ):
                            return (
                                True,
                                f"时间窗口内重复 ({'永久' if window_hours <= 0 else str(window_hours)+'小时'})",
                            )

            # 数据库检查
            exists = await self.repo.exists_media_signature(str(target_chat_id), signature)
            if exists: return True, "数据库中存在"
            # 冷区兜底：若开启永久窗口（time_window_hours<=0）或热区未命中时可进一步查询归档
            try:
                if config.get("time_window_hours", 24) <= 0:
                    from utils.bloom_index import bloom

                    # 先用 Bloom 判断可能存在，再做冷查确认
                    if bloom.probably_contains(
                        "media_signatures", str(target_chat_id), str(signature)
                    ):
                        from utils.archive_store import query_parquet_duckdb
                        from core.helpers.metrics import DEDUP_HITS_TOTAL, DEDUP_QUERIES_TOTAL

                        DEDUP_QUERIES_TOTAL.labels(method="signature").inc()
                        rows = query_parquet_duckdb(
                            "media_signatures",
                            "chat_id = ? AND signature = ?",
                            [str(target_chat_id), str(signature)],
                            columns=["chat_id"],
                            order_by="created_at DESC",
                            limit=1,
                            max_days=int(os.getenv("ARCHIVE_COLD_LOOKBACK_DAYS", "30")),
                        )
                        if rows:
                            DEDUP_HITS_TOTAL.labels(method="signature").inc()
                            return True, "归档冷区命中"
            except Exception:
                pass
            return False, ""

        except Exception as e:
            logger.debug(f"签名重复检查失败: {e}")
            return False, ""

    async def _check_content_hash_duplicate(
        self, content_hash: str, target_chat_id: int, config: Dict
    ) -> Tuple[bool, str]:
        """检查内容哈希重复"""
        try:
            cache_key = str(target_chat_id)
            if cache_key in self.content_hash_cache:
                if content_hash in self.content_hash_cache[cache_key]:
                    last_seen = self.content_hash_cache[cache_key][content_hash]
                    window_hours = config.get("time_window_hours", 24)
                    # 永久窗口：<=0 视为永久
                    if (
                        window_hours <= 0
                        or time.time() - last_seen < window_hours * 3600
                    ):
                        return (
                            True,
                            f"内容哈希重复 ({'永久' if window_hours <= 0 else str(window_hours)+'小时内'})",
                        )
            # 冷区兜底：永久窗口或热区未命中时查询归档
            try:
                if config.get("time_window_hours", 24) <= 0:
                    from utils.bloom_index import bloom

                    if bloom.probably_contains(
                        "media_signatures", str(target_chat_id), str(content_hash)
                    ):
                        from utils.archive_store import query_parquet_duckdb
                        from core.helpers.metrics import DEDUP_HITS_TOTAL, DEDUP_QUERIES_TOTAL

                        DEDUP_QUERIES_TOTAL.labels(method="content_hash").inc()
                        rows = query_parquet_duckdb(
                            "media_signatures",
                            "chat_id = ? AND content_hash = ?",
                            [str(target_chat_id), str(content_hash)],
                            columns=["chat_id"],
                            order_by="created_at DESC",
                            limit=1,
                            max_days=int(os.getenv("ARCHIVE_COLD_LOOKBACK_DAYS", "30")),
                        )
                        if rows:
                            DEDUP_HITS_TOTAL.labels(method="content_hash").inc()
                            return True, "归档冷区命中"
            except Exception:
                pass
            return False, ""

        except Exception as e:
            logger.debug(f"内容哈希检查失败: {e}")
            return False, ""

    def _get_lsh_forest(self, chat_id: str) -> Any:
        # 内部方法获取对应会话的索引
        if chat_id not in self.lsh_forests:
            try:
                from utils.algorithm.lsh_forest import LSHForest
                # 使用默认 8 棵树，前缀长度根据 Hamming 阈值调整
                # 这里我们保持默认 64bit 处理，LSHForest 内部处理排列
                self.lsh_forests[chat_id] = LSHForest(num_trees=8, prefix_length=64)
            except Exception:
                return None
        return self.lsh_forests[chat_id]

    async def _check_similarity_duplicate(
        self, message_obj, target_chat_id: int, config: Dict
    ) -> Tuple[bool, str]:
        """检查相似度重复"""
        try:
            if not hasattr(message_obj, "message") or not message_obj.message:
                return False, ""

            current_text = self._clean_text_for_hash(
                message_obj.message,
                strip_numbers=self.config.get("strip_numbers", True),
            )
            min_len = int(self.config.get("min_text_length", 10))
            if len(current_text) < min_len:  # 太短的文本不检查相似度
                return False, ""

            # 从文本缓存中查找相似文本
            cache_key = str(target_chat_id)
            if cache_key not in self.text_cache:
                return False, ""

            threshold = config.get("similarity_threshold", 0.85)
            window_hours = config.get("time_window_hours", 24)
            current_time = time.time()

            # 可选：先用固定长度指纹做预筛，O(N) 汉明距离，比精配更快
            current_fp = None
            comparisons = 0
            if config.get("enable_text_fingerprint", True):
                try:
                    current_fp = self._compute_text_fingerprint(
                        current_text, int(config.get("fingerprint_ngram", 3))
                    )
                    idx = self._get_lsh_forest(cache_key)
                    if idx and current_fp is not None:
                        # 使用 LSHForest 进行近似查询
                        # 返回 doc_id 列表，这里我们存的是 timestamp
                        hits = idx.query(current_fp, top_k=5)
                        if hits:
                            for ts_str in hits:
                                try:
                                    ts = float(ts_str)
                                except ValueError:
                                    continue
                                
                                if window_hours > 0 and current_time - ts > window_hours * 3600:
                                    continue
                                
                                # LSH 命中即视为相似 (Phase 5 策略：信任 SimHash 以支持百万级)
                                # 如果需要更精确，可以去 text_cache 捞取 (但 text_cache 可能已被截断)
                                
                                # 尝试在 text_cache 中找回原文进行核对 (Best Effort)
                                # 如果找不到原文，鉴于 LSH/SimHash 的强去重性质，我们也认作重复
                                prev_text = None
                                if cache_key in self.text_cache:
                                    for item in self.text_cache[cache_key]:
                                        if abs(item['ts'] - ts) < 0.001:
                                            prev_text = item['text']
                                            break
                                
                                if prev_text:
                                    # 有原文，进行精确比对
                                    sim = self._calculate_text_similarity(current_text, prev_text)
                                    if sim >= config.get("similarity_threshold", 0.85):
                                        try:
                                            from core.helpers.metrics import DEDUP_FP_HITS_TOTAL
                                            DEDUP_FP_HITS_TOTAL.labels(algo="lsh_forest").inc()
                                        except Exception:
                                            pass
                                        return True, f"指纹索引命中且内容校验通过 ({sim:.2f})"
                                else:
                                    # 原文已丢失，但 LSH 强匹配 -> 判定重复 (信任 SimHash)
                                    # 这里假设 LSH 的 recall 主要是真阳性
                                    return True, "LSH索引命中 (原文已归档)"

                except Exception as e:
                    logger.debug(f"SimHashIndex 检查失败: {e}")

            # 检查最近的消息（倒序，优先比较最新的）
            comparisons = 0
            curr_len = len(current_text)

            for item in reversed(self.text_cache[cache_key]):
                ts = item.get("ts")
                # 永久窗口：不会因时间过期而跳过
                if window_hours > 0 and current_time - ts > window_hours * 3600:
                    continue
                prev_text = item.get("text", "")
                prev_len = len(prev_text)
                if not prev_len:
                    continue
                if prev_text == current_text:
                    return True, "文本完全一致"

                # ✅ 优化：数学剪枝
                # 计算长度差异比率。如果长度差占比超过 (1 - 阈值)，则不可能匹配。
                # 举例：阈值 0.8，curr=100。如果 prev < 80 或 prev > 125，则必不匹配。
                # Jaccard 上限估算：min_len / max_len < threshold
                if prev_len < curr_len:
                    upper_bound = prev_len / curr_len
                else:
                    upper_bound = curr_len / prev_len

                if upper_bound < threshold:
                    continue  # 跳过昂贵的详细比对

                # 控制精确比较的上限，避免 O(N) 过大
                if comparisons >= int(config.get("max_similarity_checks", 50)):
                    break
                similarity = self._calculate_text_similarity(current_text, prev_text)
                comparisons += 1
                if similarity >= threshold:
                    return True, f"文本相似度 {similarity:.2f} ≥ {threshold}"

            try:
                from core.helpers.metrics import DEDUP_SIMILARITY_COMPARISONS

                DEDUP_SIMILARITY_COMPARISONS.observe(float(comparisons))
            except Exception:
                pass
            return False, ""
        except Exception as e:
            logger.debug(f"相似度检查失败: {e}")
            return False, ""

    async def _check_video_duplicate_by_file_id(self, file_id: str, target_chat_id: int) -> bool:
        try:
            res = await self.repo.find_by_file_id_or_hash(str(target_chat_id), file_id=file_id)
            return res is not None
        except Exception: return False

    async def _check_video_duplicate_by_hash(self, vhash: str, target_chat_id: int) -> bool:
        try:
            res = await self.repo.find_by_file_id_or_hash(str(target_chat_id), content_hash=vhash)
            return res is not None
        except Exception: return False

    async def _compute_video_partial_hash(
        self, message_obj, partial_bytes: int
    ) -> Optional[str]:
        """优化版：流式下载视频头尾部分字节并计算组合哈希，避免全量下载"""
        logger.debug("开始计算视频部分哈希...")
        try:
            if not getattr(message_obj, "media", None):
                logger.debug("消息无媒体对象，跳过哈希计算")
                return None
            from core.helpers.metrics import VIDEO_PARTIAL_HASH_SECONDS

            _start = time.time()
            # 获取文件总大小
            doc = getattr(message_obj, "document", None)
            if not doc and hasattr(message_obj, "video"):
                logger.debug("从video字段获取媒体对象")
                doc = message_obj.video
            if not doc:
                logger.debug("无法获取媒体对象，跳过哈希计算")
                return None
            total_size = getattr(doc, "size", 0)
            logger.debug(f"视频总大小: {total_size}字节")
            if total_size == 0:
                logger.debug("视频大小为0，跳过哈希计算")
                return None

            # ✅ 优化：使用 xxh64 替代 md5
            if _HAS_XXHASH:
                logger.debug("使用xxh64算法计算哈希")
                h = xxhash.xxh64()
            else:
                logger.debug("使用md5算法计算哈希")
                import hashlib as _hash

                h = _hash.md5()

            read_len = min(partial_bytes, total_size)
            logger.debug(f"每次读取字节数: {read_len}")
            try:
                client = getattr(message_obj, "client", None)
                if not client:
                    logger.debug("无法获取客户端对象，跳过哈希计算")
                    return None
                logger.debug("开始下载视频头部数据...")
                # 头部
                head_data = bytearray()
                async for chunk in client.iter_download(doc, limit=read_len):
                    head_data.extend(chunk)
                    logger.debug(f"已下载头部数据: {len(head_data)}/{read_len}字节")
                logger.debug(f"头部数据下载完成，共 {len(head_data)} 字节")
                h.update(head_data)
                # 尾部或中间段
                if total_size > read_len * 2:
                    logger.debug("视频较大，下载尾部数据...")
                    offset = total_size - read_len
                    tail_data = bytearray()
                    async for chunk in client.iter_download(
                        doc, offset=offset, limit=read_len
                    ):
                        tail_data.extend(chunk)
                        logger.debug(f"已下载尾部数据: {len(tail_data)}/{read_len}字节")
                    logger.debug(f"尾部数据下载完成，共 {len(tail_data)} 字节")
                    h.update(tail_data)
                elif total_size > read_len:
                    logger.debug("视频中等大小，下载中间段数据...")
                    mid_offset = total_size // 2
                    mid_data = bytearray()
                    async for chunk in client.iter_download(
                        doc, offset=mid_offset, limit=read_len
                    ):
                        mid_data.extend(chunk)
                        logger.debug(
                            f"已下载中间段数据: {len(mid_data)}/{read_len}字节"
                        )
                    logger.debug(f"中间段数据下载完成，共 {len(mid_data)} 字节")
                    h.update(mid_data)
            except Exception as e:
                logger.error(f"流式下载部分内容失败: {e}")
                return None
            try:
                VIDEO_PARTIAL_HASH_SECONDS.observe(max(0.0, time.time() - _start))
            except Exception:
                pass
            hash_result = h.hexdigest()
            logger.debug(
                f"视频部分哈希计算完成，结果: {hash_result}，耗时: {time.time() - _start:.3f}s"
            )
            return hash_result
        except Exception as e:
            logger.error(f"计算视频部分哈希失败: {e}")
            return None

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        # 1. 优先使用 SimHash (O(1) 记忆型算法)
        if self.simhash_engine:
            try:
                # 注意：这里如果能提前算好 fp 更好，但在比较时算也行
                fp1 = self.simhash_engine.build_fingerprint(text1)
                fp2 = self.simhash_engine.build_fingerprint(text2)
                return self.simhash_engine.similarity(fp1, fp2)
            except Exception as e:
                logger.debug(f"SimHash 计算失败: {e}")

        # 2. 备选方案
        try:
            if _HAS_RAPIDFUZZ:
                return float(fuzz.token_set_ratio(text1, text2)) / 100.0

            # 使用 Token-based Jaccard Similarity，复杂度 O(N + M)
            # 简单的空格分词（因为 _clean_text_for_hash 已经处理过标点）
            set1 = set(text1.split())
            set2 = set(text2.split())

            if not set1 or not set2:
                return 0.0

            intersection = len(set1 & set2)
            union = len(set1 | set2)

            return intersection / union if union > 0 else 0.0

        except Exception:
            return 0.0

    async def _record_message(
        self,
        message_obj,
        target_chat_id: int,
        signature: Optional[str],
        content_hash: Optional[str],
    ):
        """记录消息到缓存"""
        try:
            current_time = time.time()
            cache_key = str(target_chat_id)

            # 记录签名
            if signature:
                if cache_key not in self.time_window_cache:
                    self.time_window_cache[cache_key] = OrderedDict()
                self.time_window_cache[cache_key][signature] = current_time
                self.time_window_cache[cache_key].move_to_end(signature)

            # 记录内容哈希
            if content_hash:
                if cache_key not in self.content_hash_cache:
                    self.content_hash_cache[cache_key] = OrderedDict()
                self.content_hash_cache[cache_key][content_hash] = current_time
                self.content_hash_cache[cache_key].move_to_end(content_hash)

            # [Optimization] 文本 SimHash 指纹索引化
            if hasattr(message_obj, "message") and message_obj.message:
                text = message_obj.message
                cleaned = self._clean_text_for_hash(text)
                if cleaned:
                    fp = self._compute_text_fingerprint(cleaned)
                    if fp is not None:
                        idx = self._get_simhash_index(cache_key)
                        if idx:
                            # 在索引中存储 (text, timestamp)
                            idx.add((cleaned, current_time), fp)

            # 写入持久化缓存（用于跨重启去重热命中）
            try:
                await self._write_pcache(signature, content_hash, cache_key)
            except Exception:
                pass

            # 视频：持久化记录 file_id 与内容哈希（若有），便于后续判重
            try:
                from datetime import datetime

                is_video = (hasattr(message_obj, "video") and message_obj.video) or (
                    hasattr(message_obj, "document")
                    and message_obj.document
                    and getattr(getattr(message_obj, "document"), "mime_type", "")
                    and str(message_obj.document.mime_type).startswith("video/")
                )
                if is_video:
                    file_id = getattr(message_obj, "_tf_file_id", None)
                    vhash = getattr(message_obj, "_tf_content_hash", None)
                    # 构建尽量稳定的签名
                    stable_sig = (
                        signature
                        or (f"video:{file_id}" if file_id else None)
                        or (f"video_hash:{vhash}" if vhash else None)
                    )
                    if stable_sig:
                        # 提取一些附加属性
                        duration = int(
                            getattr(getattr(message_obj, "video", None), "duration", 0)
                            or 0
                        )
                        width = int(
                            getattr(getattr(message_obj, "video", None), "w", 0) or 0
                        )
                        height = int(
                            getattr(getattr(message_obj, "video", None), "h", 0) or 0
                        )
                        mime_type = None
                        file_size = None
                        file_name = None
                        if hasattr(message_obj, "document") and getattr(
                            message_obj, "document"
                        ):
                            mime_type = getattr(message_obj.document, "mime_type", None)
                            file_size = getattr(message_obj.document, "size", None)
                            file_name = getattr(message_obj.document, "file_name", None)

                        # ✅ 优化：仅加入内存 Buffer，不立即写库
                        payload = {
                            "chat_id": str(target_chat_id),
                            "signature": stable_sig,
                            "file_id": str(file_id) if file_id else None,
                            "content_hash": str(vhash) if vhash else None,
                            "message_id": getattr(message_obj, "id", None),
                            "media_type": "video",
                            "file_size": file_size,
                            "file_name": file_name,
                            "mime_type": mime_type,
                            "duration": duration,
                            "width": width,
                            "height": height,
                            "created_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat(),
                            "last_seen": datetime.utcnow().isoformat(),
                            "count": 1,
                        }
                        async with self._buffer_lock:
                            self._write_buffer.append(payload)

                        # 确保后台任务在运行
                        await self._ensure_flush_task()
            except Exception as pe:
                logger.debug(f"持久化视频签名失败: {pe}")

            # 记录文本（用于相似度判重）
            if hasattr(message_obj, "message") and message_obj.message:
                cleaned_text = self._clean_text_for_hash(
                    message_obj.message,
                    strip_numbers=self.config.get("strip_numbers", True),
                )
                min_len = int(self.config.get("min_text_length", 10))
                if len(cleaned_text) >= min_len:
                    if cache_key not in self.text_cache:
                        self.text_cache[cache_key] = []
                    self.text_cache[cache_key].append(
                        {"text": cleaned_text, "ts": current_time}
                    )
                    # 控制每个会话的文本缓存上限
                    max_size = int(self.config.get("max_text_cache_size", 300))
                    if len(self.text_cache[cache_key]) > max_size:
                        overflow = len(self.text_cache[cache_key]) - max_size
                        if overflow > 0:
                            self.text_cache[cache_key] = self.text_cache[cache_key][
                                overflow:
                            ]
                    # 记录文本指纹（SimHash）
                    try:
                        if self.config.get("enable_text_fingerprint", True):
                            fp = self._compute_text_fingerprint(
                                cleaned_text,
                                int(self.config.get("fingerprint_ngram", 3)),
                            )
                            if fp is not None:
                                if cache_key not in self.text_fp_cache:
                                    self.text_fp_cache[cache_key] = []
                                self.text_fp_cache[cache_key].append(
                                    {"fp": fp, "ts": current_time}
                                )
                                fp_max = int(
                                    self.config.get("max_text_fp_cache_size", 500)
                                )
                                self.text_fp_cache[cache_key] = self.text_fp_cache[
                                        cache_key
                                    ][-fp_max:]
                                
                                # ✅ 将指纹加入 LSH Forest
                                forest = self._get_lsh_forest(cache_key)
                                if forest:
                                    # doc_id 存为 timestamp 字符串
                                    forest.add(str(current_time), fp)
                                    
                    except Exception:
                        pass

        except Exception as e:
            logger.debug(f"记录消息失败: {e}")

    async def _check_pcache_hit(
        self, kind: str, target_chat_id: int, value: str
    ) -> bool:
        """检查持久化缓存是否命中。kind: 'sig' | 'hash'"""
        try:
            if not self.config.get("enable_persistent_cache", True):
                logger.debug("持久化缓存已禁用")
                return False
            from repositories.persistent_cache import get_persistent_cache

            pc = get_persistent_cache()
            key = f"dedup:{kind}:{target_chat_id}:{value}"
            logger.debug(f"检查持久化缓存，key: {key}")
            result = pc.get(key) is not None
            logger.debug(f"持久化缓存检查结果: {result}")
            return result
        except Exception as e:
            logger.debug(f"检查持久化缓存失败: {e}")
            return False

    async def _write_pcache(
        self, signature: Optional[str], content_hash: Optional[str], cache_chat_key: str
    ) -> None:
        """将签名或内容哈希写入持久化缓存，带 TTL。"""
        if not self.config.get("enable_persistent_cache", True):
            logger.debug("持久化缓存已禁用，跳过写入")
            return
        try:
            from repositories.persistent_cache import dumps_json, get_persistent_cache

            pc = get_persistent_cache()
            ttl = int(self.config.get("persistent_cache_ttl_seconds", 30 * 24 * 3600))
            logger.debug(f"开始写入持久化缓存，TTL: {ttl}秒")
            # cache_chat_key 已是 str(target_chat_id)
            if signature:
                key = f"dedup:sig:{cache_chat_key}:{signature}"
                logger.debug(f"写入持久化缓存，key: {key}")
                pc.set(key, dumps_json({"ts": int(time.time())}), ttl)
            if content_hash:
                key = f"dedup:hash:{cache_chat_key}:{content_hash}"
                logger.debug(f"写入持久化缓存，key: {key}")
                pc.set(key, dumps_json({"ts": int(time.time())}), ttl)
            logger.debug("持久化缓存写入完成")
        except Exception as e:
            logger.debug(f"写入持久化缓存失败: {e}")
            pass

    async def _ensure_flush_task(self):
        """确保后台刷写任务在运行"""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_worker())

    async def _flush_worker(self):
        """后台刷写任务：定期将内存缓冲区中的数据批量写入数据库"""
        while True:
            await asyncio.sleep(2.0)  # 每2秒刷写一次
            async with self._buffer_lock:
                if not self._write_buffer:
                    continue
                batch = self._write_buffer[:]
                self._write_buffer.clear()

            # 执行批量插入
            try: await self.repo.batch_add(batch)
            except Exception as e: logger.error(f"批量写入指纹失败: {e}")

    async def _cleanup_cache_if_needed(self):
        """定期清理过期缓存"""
        try:
            current_time = time.time()
            if current_time - self.last_cleanup < self.config["cache_cleanup_interval"]:
                return

            max_age = self.config["time_window_hours"] * 3600 * 2  # 保留2倍时间窗口

            # 清理时间窗口缓存
            for chat_id in list(self.time_window_cache.keys()):
                cache = self.time_window_cache[chat_id]
                # 利用有序性，仅处理头部过期项
                while cache:
                    # peek 头部元素 (key, ts)
                    key, timestamp = next(iter(cache.items()))
                    if current_time - timestamp > max_age:
                        cache.popitem(last=False)  # 弹出头部
                    else:
                        break  # 遇到第一个未过期的，后续都不用检查

                if not cache:
                    del self.time_window_cache[chat_id]

            # 清理内容哈希缓存
            for chat_id in list(self.content_hash_cache.keys()):
                cache = self.content_hash_cache[chat_id]
                # 利用有序性，仅处理头部过期项
                while cache:
                    # peek 头部元素 (key, ts)
                    key, timestamp = next(iter(cache.items()))
                    if current_time - timestamp > max_age:
                        cache.popitem(last=False)  # 弹出头部
                    else:
                        break  # 遇到第一个未过期的，后续都不用检查

                if not cache:
                    del self.content_hash_cache[chat_id]

            # 清理文本缓存
            for chat_id in list(self.text_cache.keys()):
                items = self.text_cache[chat_id]
                # 仅保留在有效期内的
                items = [
                    it for it in items if current_time - it.get("ts", 0) <= max_age
                ]
                if items:
                    # 再次确保不超过上限
                    max_size = int(self.config.get("max_text_cache_size", 300))
                    if len(items) > max_size:
                        items = items[-max_size:]
                    self.text_cache[chat_id] = items
                else:
                    del self.text_cache[chat_id]
            # 清理文本指纹缓存
            for chat_id in list(self.text_fp_cache.keys()):
                items = self.text_fp_cache[chat_id]
                items = [
                    it for it in items if current_time - it.get("ts", 0) <= max_age
                ]
                if items:
                    fp_max = int(self.config.get("max_text_fp_cache_size", 500))
                    if len(items) > fp_max:
                        items = items[-fp_max:]
                    self.text_fp_cache[chat_id] = items
                else:
                    del self.text_fp_cache[chat_id]

            self.last_cleanup = current_time
            logger.debug("智能去重缓存清理完成")

        except Exception as e:
            logger.error(f"缓存清理失败: {e}")

    def get_stats(self) -> Dict:
        """获取去重统计信息"""
        try:
            total_signatures = sum(
                len(cache) for cache in self.time_window_cache.values()
            )
            total_hashes = sum(len(cache) for cache in self.content_hash_cache.values())
            total_texts = sum(len(items) for items in self.text_cache.values())

            return {
                "cached_signatures": total_signatures,
                "cached_content_hashes": total_hashes,
                "cached_texts": total_texts,
                "cached_text_fps": sum(
                    len(items) for items in self.text_fp_cache.values()
                ),
                "tracked_chats": len(self.time_window_cache),
                "config": self.config.copy(),
                "last_cleanup": self.last_cleanup,
            }
        except Exception:
            return {}

    def update_config(self, new_config: Dict):
        """更新配置并持久化"""
        self.config.update(new_config)
        logger.info(f"智能去重配置已更新: {self.config}")

        # 持久化配置到数据库
        try:
            self._save_config_to_db()
        except Exception as e:
            logger.warning(f"保存去重配置到数据库失败: {e}")

    def _save_config_to_db(self):
        """保存配置到数据库"""
        try:
            import json

            from models.models import SessionManager, SystemConfiguration

            with SessionManager() as session:
                # 查找或创建配置记录
                config_record = (
                    session.query(SystemConfiguration)
                    .filter_by(key="smart_dedup_config")
                    .first()
                )

                if not config_record:
                    config_record = SystemConfiguration(
                        key="smart_dedup_config", value=json.dumps(self.config)
                    )
                    session.add(config_record)
                else:
                    config_record.value = json.dumps(self.config)

                session.commit()
                logger.debug("智能去重配置已保存到数据库")

        except Exception as e:
            logger.error(f"保存去重配置失败: {e}")

    def _load_config_from_db(self):
        """从数据库加载配置"""
        try:
            import json

            from models.models import SessionManager, SystemConfiguration

            with SessionManager() as session:
                config_record = (
                    session.query(SystemConfiguration)
                    .filter_by(key="smart_dedup_config")
                    .first()
                )

                if config_record and config_record.value:
                    db_config = json.loads(config_record.value)
                    # 合并数据库配置和默认配置
                    self.config.update(db_config)
                    logger.info(f"从数据库加载智能去重配置: {self.config}")

        except Exception as e:
            logger.warning(f"从数据库加载去重配置失败: {e}")

    def reset_to_defaults(self):
        """重置为默认配置"""
        self.config = {
            "enable_time_window": True,
            "time_window_hours": 24,
            "similarity_threshold": 0.85,
            "enable_content_hash": True,
            "enable_smart_similarity": True,
            "cache_cleanup_interval": 3600,
            "max_text_cache_size": 300,
            "min_text_length": 10,
            "strip_numbers": True,
            "enable_text_fingerprint": True,
            "fingerprint_ngram": 3,
            "fingerprint_hamming_threshold": 3,
            "max_text_fp_cache_size": 500,
            "max_similarity_checks": 50,
            "enable_text_similarity_for_video": False,
            "enable_video_file_id_check": True,
            "enable_video_partial_hash_check": True,
            "video_partial_hash_bytes": 262144,
            "disable_similarity_for_grouped": True,
        }
        self._save_config_to_db()
        logger.info("智能去重配置已重置为默认值")

    def _compute_text_fingerprint(
        self, cleaned_text: str, ngram: int = 3
    ) -> Optional[int]:
        """基于词级 n-gram 的简易 SimHash（64位）。"""
        try:
            tokens = cleaned_text.split()
            if not tokens:
                return None
            shingles = [
                " ".join(tokens[i : i + ngram])
                for i in range(max(1, len(tokens) - ngram + 1))
            ]
            if not shingles:
                shingles = tokens
            vector = [0] * 64

            # ✅ 优化：使用 xxHash 替代 MD5
            if _HAS_XXHASH:
                for s in shingles:
                    # xxh64 直接返回 int，速度极快
                    h = xxhash.xxh64(s.encode("utf-8")).intdigest()
                    for i in range(64):
                        if (h >> i) & 1:
                            vector[i] += 1
                        else:
                            vector[i] -= 1
            else:
                # 原有逻辑...
                for s in shingles:
                    h = int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)
                    for i in range(64):
                        if (h >> i) & 1:
                            vector[i] += 1
                        else:
                            vector[i] -= 1

            fp = 0
            for i, v in enumerate(vector):
                if v > 0:
                    fp |= 1 << i
            return fp
        except Exception:
            return None

    def _hamming_distance64(self, a: int, b: int) -> int:
        if _HAS_NUMBA:
            return _fast_hamming_64(a, b)
        xor_val = (a ^ b) & 0xFFFFFFFFFFFFFFFF

        # Python 3.10+ 原生支持 (极速)
        if hasattr(int, "bit_count"):
            return xor_val.bit_count()

        # 回退算法 (Kernighan's Algorithm / Brian Kernighan's way)
        # 对于差异较小的指纹（去重场景），此算法只需循环 "差异位数" 次，远少于 64 次
        count = 0
        while xor_val:
            xor_val &= xor_val - 1
            count += 1
        return count

    async def _strict_verify_video_features(
        self,
        target_chat_id: int,
        message_obj,
        file_id: Optional[str],
        vhash: Optional[str],
        config: Dict,
    ) -> bool:
        """在哈希命中后进行严格复核：比较 duration/分辨率/大小范围 等特征。

        容忍度通过配置控制：
        - video_duration_tolerance_sec
        - video_resolution_tolerance_px
        - video_size_bucket_tolerance
        """
        try:
            # 读取当前消息的特征
            duration = int(
                getattr(getattr(message_obj, "video", None), "duration", 0) or 0
            )
            width = int(getattr(getattr(message_obj, "video", None), "w", 0) or 0)
            height = int(getattr(getattr(message_obj, "video", None), "h", 0) or 0)
            size_val = None
            if hasattr(message_obj, "document") and getattr(message_obj, "document"):
                try:
                    size_val = int(getattr(message_obj.document, "size", 0) or 0)
                except Exception:
                    size_val = None
            size_bucket = self._get_size_range(size_val or 0)
            # 查找历史一条匹配记录用于对比
            from repositories.db_operations import DBOperations
            from models.models import AsyncSessionManager

            # 使用异步上下文管理器
            async with AsyncSessionManager() as session:
                db_ops = await DBOperations.create()
                rec = await db_ops.find_media_record_by_fileid_or_hash(
                    session, str(target_chat_id), file_id=file_id, content_hash=vhash
                )
                if not rec:
                    return True  # 没有可以对比的记录时，不阻断
                tol_d = int(config.get("video_duration_tolerance_sec", 2))
                tol_r = int(config.get("video_resolution_tolerance_px", 8))
                tol_s = int(config.get("video_size_bucket_tolerance", 1))
                # 历史特征
                h_d = int(getattr(rec, "duration", 0) or 0)
                h_w = int(getattr(rec, "width", 0) or 0)
                h_h = int(getattr(rec, "height", 0) or 0)
                h_bucket = self._get_size_range(int(getattr(rec, "file_size", 0) or 0))
                # 比较
                if abs(duration - h_d) > tol_d:
                    return False
                if (width and h_w) and abs(width - h_w) > tol_r:
                    return False
                if (height and h_h) and abs(height - h_h) > tol_r:
                    return False
                # bucket 容忍 1 级（可配置）
                if size_bucket and h_bucket:
                    if (
                        abs(
                            self._size_bucket_index(size_bucket)
                            - self._size_bucket_index(h_bucket)
                        )
                        > tol_s
                    ):
                        return False
                return True
        except Exception:
            return True

    async def _check_video_hash_pcache(self, file_id: str) -> Optional[str]:
        """从持久化缓存中读取视频 partial-hash。"""
        try:
            from repositories.persistent_cache import get_persistent_cache, loads_json

            pc = get_persistent_cache()
            key = f"video:hash:{file_id}"
            logger.debug(f"检查视频哈希持久化缓存，key: {key}")
            raw = pc.get(key)
            if raw:
                logger.debug(f"视频哈希持久化缓存命中，key: {key}")
                data = loads_json(raw)
                if isinstance(data, dict):
                    hash_value = data.get("hash")
                    logger.debug(f"从缓存中获取到视频哈希: {hash_value}")
                    return hash_value
            logger.debug(f"视频哈希持久化缓存未命中，key: {key}")
        except Exception as e:
            logger.debug(f"检查视频哈希持久化缓存失败: {e}")
            return None
        return None

    async def _write_video_hash_pcache(
        self, file_id: str, vhash: str, ttl_seconds: int
    ) -> None:
        """写入视频 partial-hash 到持久化缓存。"""
        try:
            from repositories.persistent_cache import dumps_json, get_persistent_cache

            pc = get_persistent_cache()
            key = f"video:hash:{file_id}"
            ttl = max(60, int(ttl_seconds))
            logger.debug(
                f"写入视频哈希持久化缓存，key: {key}, hash: {vhash}, TTL: {ttl}秒"
            )
            pc.set(key, dumps_json({"hash": vhash, "ts": int(time.time())}), ttl)
            logger.debug(f"视频哈希持久化缓存写入完成，key: {key}")
        except Exception as e:
            logger.debug(f"写入视频哈希持久化缓存失败: {e}")
            pass


    async def remove_message(self, message_obj, target_chat_id: int):
        """Remove message from cache (Rollback)"""
        try:
            cache_key = str(target_chat_id)
            signature = self._generate_signature(message_obj)
            content_hash = self._generate_content_hash(message_obj)
            
            # Remove from Memory Cache
            if signature and cache_key in self.time_window_cache:
                self.time_window_cache[cache_key].pop(signature, None)
            
            if content_hash and cache_key in self.content_hash_cache:
                self.content_hash_cache[cache_key].pop(content_hash, None)
                
            # Remove from Persistent Cache
            if self.config.get("enable_persistent_cache", True):
                try:
                    from repositories.persistent_cache import get_persistent_cache
                    pc = get_persistent_cache()
                    if signature:
                        pc.delete(f"dedup:sig:{target_chat_id}:{signature}")
                    if content_hash:
                        pc.delete(f"dedup:hash:{target_chat_id}:{content_hash}")
                except Exception:
                    pass
            
            # Remove from Write Buffer (if not flushed yet)
            async with self._buffer_lock:
                 self._write_buffer = [
                     item for item in self._write_buffer 
                     if not (item.get('signature') == signature and item.get('content_hash') == content_hash)
                 ]
                 
            logger.debug(f"Rolled back dedup status for chat {target_chat_id}")
        except Exception as e:
            logger.error(f"Failed to rollback dedup: {e}")

# 全局智能去重器实例
smart_deduplicator = SmartDeduplicator()
