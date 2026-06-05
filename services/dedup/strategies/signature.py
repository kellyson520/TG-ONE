from datetime import timedelta
import time
from typing import Optional
from services.dedup.strategies.base import BaseDedupStrategy
from services.dedup.types import DedupContext, DedupResult

class SignatureStrategy(BaseDedupStrategy):
    async def process(self, ctx: DedupContext) -> Optional[DedupResult]:
        """
        处理签名去重逻辑
        """
        message_obj = ctx.message_obj
        target_chat_id = ctx.target_chat_id
        config = ctx.config
        
        # 1. 检查是否跳过签名
        if config.skip_media_sig:
            return None
            
        # 2. 生成签名
        from services.dedup.tools import generate_signature
        signature = generate_signature(message_obj)
        
        if not signature:
            return None
            
        if ctx.bloom_filter:
            # 格式兼容：某些地方存 sig:chat:val，某些地方存 val
            # 这里对应 engine.py:351 存的是 sig:{target_chat_id}:{signature}
            bloom_key = f"sig:{target_chat_id}:{signature}"
            if bloom_key not in ctx.bloom_filter:
                # 只有未命中才确定不重复，命中则继续深挖 (L1, L2, L3)
                return None
        
        # 4. 检查持久化缓存 (L2)
        pcache_key = f"sig:{target_chat_id}:{signature}"
        if await ctx.pcache_repo.get(pcache_key):
             return DedupResult(True, "签名重复: persistent cache 命中", "signature", signature)

        # 5. 检查内存缓存 (L1) - 时间窗口
        if config.enable_time_window:
            cache_key = str(target_chat_id)
            if cache_key in ctx.time_window_cache:
                sigs = ctx.time_window_cache[cache_key]
                if signature in sigs:
                    last_seen_ts = sigs[signature]
                    # 检查是否在窗口内
                    window_hours = config.time_window_hours
                    diff = time.time() - last_seen_ts
                    
                    if window_hours < 0: # 永久
                        return DedupResult(True, "时间窗口内重复 (永久)", "signature", signature)
                    elif diff < window_hours * 3600:
                         return DedupResult(True, f"时间窗口内重复 ({window_hours}小时)", "signature", signature)
        
        # 6. 检查数据库 (L3)
        exists = await ctx.repo.exists_media_signature(str(target_chat_id), signature)
        if exists:
            # 数据库命中
            return DedupResult(True, "数据库中存在", "signature", signature)
            
        # 7. 冷区检查 (Archive/DuckDB)
        # 逻辑：只有当时间窗口设置为永久(<=0)时，才进行深度挖掘
        if config.time_window_hours <= 0: 
            try:
                from repositories.bloom_index import bloom
                if bloom.probably_contains("media_signatures", str(target_chat_id), str(signature)):
                    from repositories.archive_store import query_parquet_duckdb
                    # 限制检索范围，避免全量扫描
                    rows = query_parquet_duckdb(
                        "media_signatures",
                        "chat_id = ? AND signature = ?",
                        [str(target_chat_id), str(signature)],
                        columns=["chat_id"],
                        limit=1
                    )
                    if rows:
                        return DedupResult(True, "归档冷区命中 (DuckDB)", "signature", signature)
            except Exception as e:
                ctx.logger.warning(f"归档冷区查询失败: {e}")

        return None

    async def record(self, ctx: DedupContext, result: DedupResult):
        pass
