
import logging
import json
from typing import Optional, List
from services.dedup.strategies.base import BaseDedupStrategy
from services.dedup.types import DedupContext, DedupResult
from services.dedup.tools import generate_content_hash, generate_signature

logger = logging.getLogger(__name__)

class AlbumStrategy(BaseDedupStrategy):
    """
    相册聚合去重策略 (V4)
    处理带 grouped_id 的消息序列，通过聚合哈希检测整体相似度。
    """
    async def process(self, ctx: DedupContext) -> Optional[DedupResult]:
        config = ctx.config
        if not config.get('enable_album_dedup', True):
            return None
            
        message_obj = ctx.message_obj
        grouped_id = getattr(message_obj, 'grouped_id', None)
        if not grouped_id:
            return None
            
        target_chat_id = ctx.target_chat_id
        content_hash = generate_content_hash(message_obj)
        if not content_hash:
            return None

        # 1. 维护当前相册的内存/缓存状态
        # key: album:info:{chat_id}:{grouped_id}
        # value: List[content_hash]
        cache_key = f"album:info:{target_chat_id}:{grouped_id}"
        
        raw_state = await ctx.pcache_repo.get(cache_key)
        album_hashes = json.loads(raw_state) if raw_state else []
        
        if content_hash not in album_hashes:
            album_hashes.append(content_hash)
            await ctx.pcache_repo.set(cache_key, json.dumps(album_hashes), expire=3600) # 1小时有效期

        # 2. 实时相似度判断 (基于相册已出现部分的重复率)
        # 统计 album_hashes 中有多少个已经在数据库中存在 (作为独立重复项)
        dup_count = 0
        for h in album_hashes:
            # 这里的 check 可能会比较慢，实际实现中可以缓存 check 结果
            is_dup, _ = await ctx.repo.check_content_hash_duplicate(h, target_chat_id, config)
            if is_dup:
                dup_count += 1
        
        total = len(album_hashes)
        threshold = config.get('album_duplicate_threshold', 0.8)
        
        if total >= 2 and (dup_count / total) >= threshold:
            return DedupResult(True, f"相册聚合重复率超过 {threshold*100}% ({dup_count}/{total})", "album_cluster", grouped_id)

        return None

    async def record(self, ctx: DedupContext, result: DedupResult):
        pass
