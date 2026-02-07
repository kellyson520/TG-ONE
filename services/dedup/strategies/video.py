
from datetime import datetime
import asyncio
import logging
from typing import Optional, Dict, Any

from services.dedup.strategies.base import BaseDedupStrategy
from services.dedup.types import DedupContext, DedupResult
from services.dedup.tools import (
    extract_video_file_id, 
    is_video, 
    calculate_text_similarity,
    generate_v3_fingerprint
)
from core.helpers.metrics import DEDUP_HITS_TOTAL, VIDEO_HASH_PCACHE_HITS_TOTAL

logger = logging.getLogger(__name__)

class VideoStrategy(BaseDedupStrategy):
    async def process(self, ctx: DedupContext) -> Optional[DedupResult]:
        """高级视频去重逻辑 (FileID, SSH v4, Strict Verification)"""
        
        if ctx.config.get('skip_media_sig', False):
             return None
             
        message_obj = ctx.message_obj
        target_chat_id = ctx.target_chat_id
        config = ctx.config
        
        if not is_video(message_obj):
            return None
            
        # 1. 快速 FileID 检查
        file_id = extract_video_file_id(message_obj)
        if file_id and config.get('enable_video_file_id_check', True):
            # 1.1 PCache 命中
            pcache_key = f"video:id:{file_id}"
            if await ctx.pcache_repo.get(pcache_key):
                 return DedupResult(True, "视频FileID重复 (PCache)", "video_file_id", str(file_id))

            # 1.2 DB 查重
            if await ctx.repo.exists_video_file_id(str(target_chat_id), str(file_id)):
                try: DEDUP_HITS_TOTAL.labels(method="video_file_id").inc()
                except: pass
                # 检测到重复，回填 PCache
                await ctx.pcache_repo.set(pcache_key, "1", ttl=86400 * 30)
                return DedupResult(True, "视频FileID重复", "video_file_id", str(file_id))

        # 2. 深度 SSH v4 (Sparse-Sentinel Hash) 内容检查
        if config.get('enable_video_partial_hash_check', True):
            # 2.1 尝试获取已有的哈希结果 (来自 PCache)
            vhash = None
            if file_id:
                pcache_hash_key = f"vhash:{file_id}"
                vhash_raw = await ctx.pcache_repo.get(pcache_hash_key)
                if vhash_raw:
                    vhash = vhash_raw.decode() if isinstance(vhash_raw, bytes) else vhash_raw
                    try: VIDEO_HASH_PCACHE_HITS_TOTAL.labels(algo="ssh_v4").inc()
                    except: pass

            # 2.2 如果没有缓存，决定是否启动后台计算
            if not vhash:
                # 仅针对大于 5MB 的视频执行 
                doc = getattr(message_obj, 'video', None) or getattr(message_obj, 'document', None)
                size = int(getattr(doc, 'size', 0) or 0)
                
                if size > config.get('video_partial_hash_min_size_bytes', 5*1024*1024):
                    # 启动后台任务计算哈希并持久化，本次放行
                    task = asyncio.create_task(self._compute_and_save_hash_bg(ctx, doc, file_id))
                    ctx.bg_tasks.add(task)
                    task.add_done_callback(ctx.bg_tasks.discard)
                    return None # 异步处理，暂时不判断
            else:
                # 2.3 哈希命中，进入严格复核
                is_hash_dup = await ctx.repo.exists_media_signature(
                    str(target_chat_id), f"video_hash:{vhash}"
                )
                if is_hash_dup:
                    # 严格校验时长/分辨率
                    if await self._strict_verify(ctx, vhash, config):
                        try: DEDUP_HITS_TOTAL.labels(method="video_ssh_v4").inc()
                        except: pass
                        return DedupResult(True, "视频内容哈希重复", "video_hash", vhash)

        return None

    async def _strict_verify(self, ctx: DedupContext, vhash: str, config: Any) -> bool:
        """
        在内容哈希命中后进行物理特征复核 (Strict Verification)
        防止不同视频因采样点一致导致的哈希碰撞
        """
        if not config.get('video_strict_verify', True):
            return True
            
        msg = ctx.message_obj
        doc = getattr(msg, 'video', None) or getattr(msg, 'document', None)
        if not doc: return True

        try:
            # 1. 获取当前视频特征
            curr_dur = int(getattr(doc, 'duration', 0) or 0)
            curr_w = int(getattr(doc, 'w', 0) or 0)
            curr_h = int(getattr(doc, 'h', 0) or 0)
            curr_size = int(getattr(doc, 'size', 0) or 0)
            
            from services.dedup import tools
            curr_bucket = tools.get_size_range(curr_size)
            curr_bucket_idx = tools.size_bucket_index(curr_bucket)

            # 2. 从数据库查询历史记录元数据
            # 优先查 vhash 对应的记录
            rec = await ctx.repo.find_by_file_id_or_hash(str(ctx.target_chat_id), content_hash=vhash)
            if not rec:
                return True # 无历史记录可对比时，视为不冲突 (由哈希初步判定)

            # 3. 执行容忍度比对
            tol_d = int(config.get("video_duration_tolerance_sec", 2))
            tol_r = int(config.get("video_resolution_tolerance_px", 8))
            tol_s = int(config.get("video_size_bucket_tolerance", 1))

            # 历史特征 (rec 是 MediaSignatureDTO 或 SQLAlchemy 对象)
            hist_dur = int(getattr(rec, "duration", 0) or 0)
            hist_w = int(getattr(rec, "width", 0) or 0)
            hist_h = int(getattr(rec, "height", 0) or 0)
            hist_size = int(getattr(rec, "file_size", 0) or 0)
            hist_bucket = tools.get_size_range(hist_size)
            hist_bucket_idx = tools.size_bucket_index(hist_bucket)

            # --- 校验逻辑 ---
            # A. 时长校验
            if abs(curr_dur - hist_dur) > tol_d:
                logger.debug(f"Video verify failed: duration diff {abs(curr_dur - hist_dur)} > {tol_d}")
                return False
                
            # B. 分辨率校验 (仅当两者均有时)
            if curr_w and hist_w and abs(curr_w - hist_w) > tol_r:
                return False
            if curr_h and hist_h and abs(curr_h - hist_h) > tol_r:
                return False
                
            # C. 大小分桶校验
            if curr_bucket_idx != -1 and hist_bucket_idx != -1:
                if abs(curr_bucket_idx - hist_bucket_idx) > tol_s:
                    logger.debug(f"Video verify failed: size bucket diff {abs(curr_bucket_idx - hist_bucket_idx)} > {tol_s}")
                    return False

            return True
        except Exception as e:
            logger.warning(f"视频严格复核过程异常 (按放行处理): {e}")
            return True

    async def _compute_and_save_hash_bg(self, ctx: DedupContext, doc: Any, file_id: Optional[str]):
        """后台异步采样计算视频哈希"""
        try:
            client = getattr(ctx.message_obj, 'client', None)
            if not client or not doc: return
            
            # 5 点采样逻辑 (SSH v4)
            from services.dedup.tools import _HAS_XXHASH
            import xxhash
            import hashlib
            
            h = xxhash.xxh128() if _HAS_XXHASH else hashlib.blake2b(digest_size=16)
            total_size = doc.size
            chunk_size = 65536 # 64KB per point
            
            # 元数据盐值
            h.update(f"{getattr(doc, 'w', 0)}x{getattr(doc, 'h', 0)}|{getattr(doc, 'duration', 0)}|{total_size}".encode())
            
            offsets = [0, total_size // 4, total_size // 2, total_size * 3 // 4, max(0, total_size - chunk_size)]
            for offset in sorted(list(set(offsets))):
                async for chunk in client.iter_download(doc, offset=offset, limit=chunk_size):
                    h.update(chunk)
            
            vhash = h.hexdigest()
            # 写入 PCache
            if file_id:
                await ctx.pcache_repo.set(f"vhash:{file_id}", vhash, ttl=86400 * 180) # 180天
            
            # 记录到 DB
            await ctx.repo.add_media_signature(str(ctx.target_chat_id), f"video_hash:{vhash}", getattr(ctx.message_obj, 'id', 0))
            logger.info(f"视频后台哈希计算完成: {file_id} -> {vhash}")
            
        except Exception as e:
            logger.warning(f"视频后台哈希处理异常: {e}")

    async def record(self, ctx: DedupContext, result: DedupResult):
        pass
