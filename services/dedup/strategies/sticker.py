
import logging
from typing import Optional
from services.dedup.strategies.base import BaseDedupStrategy
from services.dedup.types import DedupContext, DedupResult
from services.dedup.tools import is_sticker, extract_sticker_id
from core.helpers.metrics import DEDUP_HITS_TOTAL

logger = logging.getLogger(__name__)

class StickerStrategy(BaseDedupStrategy):
    """
    表情包去重策略 (V4)
    专门处理 Sticker 类型消息，防止热门表情包刷屏。
    """
    async def process(self, ctx: DedupContext) -> Optional[DedupResult]:
        config = ctx.config
        if not config.get('enable_sticker_filter', True):
            return None
            
        message_obj = ctx.message_obj
        if not is_sticker(message_obj):
            return None
            
        sticker_id = extract_sticker_id(message_obj)
        if not sticker_id:
            return None
            
        target_chat_id = ctx.target_chat_id
        
        # 1. 检查 PCache (L2)
        pcache_key = f"sticker:{target_chat_id}:{sticker_id}"
        if await ctx.pcache_repo.get(pcache_key):
             return DedupResult(True, "表情包重复 (PCache)", "sticker", sticker_id)
             
        # 2. 检查 Bloom Filter (L0)
        bloom_key = f"stk:{target_chat_id}:{sticker_id}"
        if ctx.bloom_filter and bloom_key not in ctx.bloom_filter:
            return None # 确定未见过
            
        # 3. 检查数据库 (L3)
        # 表情包特征存入 media_signatures 也是可以的，通过 prefix 区分
        exists = await ctx.repo.exists_media_signature(str(target_chat_id), f"sticker:{sticker_id}")
        if exists:
            try: DEDUP_HITS_TOTAL.labels(method="sticker").inc()
            except: pass
            # 回填 PCache
            await ctx.pcache_repo.set(pcache_key, "1", expire=86400 * 7)
            return DedupResult(True, "表情包重复 (DB)", "sticker", sticker_id)
            
        return None

    async def record(self, ctx: DedupContext, result: DedupResult):
        pass
