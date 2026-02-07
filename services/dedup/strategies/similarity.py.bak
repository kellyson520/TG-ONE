from datetime import datetime
import logging
import time
from typing import Optional, Dict

from services.dedup.strategies.base import BaseDedupStrategy
from services.dedup.types import DedupContext, DedupResult
from services.dedup.tools import (
    calculate_simhash, 
    is_video, 
    calculate_text_similarity,
    clean_text_for_hash
)
from core.helpers.metrics import DEDUP_HITS_TOTAL, DEDUP_FP_HITS_TOTAL, DEDUP_SIMILARITY_COMPARISONS

logger = logging.getLogger(__name__)

class SimilarityStrategy(BaseDedupStrategy):
    async def process(self, ctx: DedupContext) -> Optional[DedupResult]:
        """高级文本相似度去重 (LSH Forest + SimHash v3 + Pruning)"""
        
        config = ctx.config
        if not config.get("enable_smart_similarity", False):
            return None
            
        message_obj = ctx.message_obj
        target_chat_id = ctx.target_chat_id
        
        # 1. 前置过滤
        if is_video(message_obj) and not config.get("enable_text_similarity_for_video", False):
            return None
            
        if getattr(message_obj, "grouped_id", None) and config.get("disable_similarity_for_grouped", True):
            return None
            
        text = getattr(message_obj, "message", "") or getattr(message_obj, "text", "")
        if not text: return None
        
        # 清洗文本
        cleaned_text = clean_text_for_hash(text, strip_numbers=config.get("strip_numbers", True))
        min_len = int(config.get("min_text_length", 10))
        curr_len = len(cleaned_text)
        if curr_len < min_len:
            return None
            
        # 2. 生成 SimHash 指纹
        current_fp = None
        if config.get("enable_text_fingerprint", True):
            current_fp = calculate_simhash(cleaned_text)
            if not current_fp: return None
            
            # --- LSH Forest 快速索引查询 (Phase 5 核心) ---
            cache_key = str(target_chat_id)
            if hasattr(ctx, 'lsh_forests') and cache_key in ctx.lsh_forests:
                forest = ctx.lsh_forests[cache_key]
                # 查询 top-k 近似项
                hits = forest.query(current_fp, top_k=5)
                if hits:
                    for doc_id in hits:
                        # doc_id 通常存的是 timestamp 或 msg_id
                        # 如果需要精确校验，可以去 text_cache 找，但这里直接命中 LSH 即视为相似
                        try: DEDUP_FP_HITS_TOTAL.labels(algo="lsh_forest").inc()
                        except: pass
                        return DedupResult(True, "LSH索引命中 (语义重复)", "similarity_lsh", current_fp)

        # 3. 内存缓存滚动比对 (带数学剪枝)
        if ctx.text_fp_cache and str(target_chat_id) in ctx.text_fp_cache:
            cache_key = str(target_chat_id)
            threshold = config.get("similarity_threshold", 0.85)
            comparisons = 0
            max_checks = int(config.get("max_similarity_checks", 50))
            
            # reversed 遍历，优先比对新消息
            for fp, meta in reversed(ctx.text_fp_cache[cache_key].items()):
                if comparisons >= max_checks: break
                
                # 数学剪枝：如果长度差异过大，则不可能相似 (Jaccard 上限)
                prev_len = meta.get('len', 0) if isinstance(meta, dict) else 0
                if prev_len:
                    upper_bound = min(prev_len, curr_len) / max(prev_len, curr_len)
                    if upper_bound < threshold:
                        continue
                
                # 计算相似度
                sim = 1.0 - (bin(current_fp ^ fp).count('1') / 64.0)
                comparisons += 1
                
                if sim >= threshold:
                    try: DEDUP_HITS_TOTAL.labels(method="similarity_memory").inc()
                    except: pass
                    return DedupResult(True, f"文本相似度命中: {sim:.2f}", "similarity", fp)

            try: DEDUP_SIMILARITY_COMPARISONS.observe(float(comparisons))
            except: pass

        return None

    async def record(self, ctx: DedupContext, result: DedupResult):
        pass
