from datetime import datetime
from typing import Optional
from services.dedup.strategies.base import BaseDedupStrategy
from services.dedup.types import DedupContext, DedupResult
from services.dedup.types import DedupContext, DedupResult
from services.dedup.tools import generate_content_hash, is_video
from core.helpers.metrics import DEDUP_HITS_TOTAL

class ContentStrategy(BaseDedupStrategy):
    async def process(self, ctx: DedupContext) -> Optional[DedupResult]:
        """处理内容哈希去重 (Text/Image/Video Content Hash)"""
        
        message_obj = ctx.message_obj
        target_chat_id = ctx.target_chat_id
        config = ctx.config
        
        # 1. 检查是否跳过内容哈希
        if not config.get("enable_content_hash", True):
            return None
            
        # 2. 生成内容哈希
        # 注意: generate_content_hash 内部已处理 skip_media_sig 逻辑降级 (Text Only)
        # 如果是视频且 enable_content_hash_for_video 关闭，则跳过
        if is_video(message_obj) and \
           not config.get("enable_content_hash_for_video", False) and \
           not config.get("skip_media_sig", False):
            # 视频且未开启视频内容哈希，也未要求降级纯文本，则跳过
            return None
            
        content_hash = generate_content_hash(message_obj)
        
        if not content_hash:
            return None
            
        # 3. 检查持久化缓存 (PCache)
        pcache_key = f"hash:{target_chat_id}:{content_hash}"
        if await ctx.pcache_repo.get(pcache_key):
             try: DEDUP_HITS_TOTAL.labels(method="content_hash_pcache").inc()
             except: pass
             return DedupResult(True, "内容重复: persistent cache 命中", "content_hash", content_hash)
             
        # 4. 检查数据库 (L3)
        is_dup, reason = await ctx.repo.check_content_hash_duplicate(content_hash, target_chat_id, config)
        if is_dup:
             try: DEDUP_HITS_TOTAL.labels(method="content_hash").inc()
             except: pass
             return DedupResult(True, f"内容重复: {reason}", "content_hash", content_hash)
             
        # 5. 检查归档 (L4)
        if config.time_window_hours <= 0:
            try:
                from repositories.bloom_index import bloom
                if bloom.probably_contains("media_signatures", str(target_chat_id), str(content_hash)):
                    from repositories.archive_store import query_parquet_duckdb
                    rows = query_parquet_duckdb(
                        "media_signatures",
                        "chat_id = ? AND content_hash = ?",
                        [str(target_chat_id), str(content_hash)],
                        columns=["chat_id"],
                        limit=1
                    )
                    if rows:
                        return DedupResult(True, "内容归档重复 (DuckDB)", "content_hash", content_hash)
            except Exception as e:
                ctx.logger.warning(f"内容哈希归档查询失败: {e}")
             
        return None

    async def record(self, ctx: DedupContext, result: DedupResult):
        pass
