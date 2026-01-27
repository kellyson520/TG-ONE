import logging
import os

logger = logging.getLogger(__name__)

# 1. 模块级缓存
_CACHED_MAX_SIZE = None


def _load_max_size():
    """加载并解析MAX_MEDIA_SIZE配置"""
    try:
        val = os.getenv("MAX_MEDIA_SIZE")
        if not val:
            logger.warning("未设置 MAX_MEDIA_SIZE，默认使用 2000MB")
            return 2000.0 * 1024 * 1024
        return float(val) * 1024 * 1024
    except Exception as e:
        logger.error(f"MAX_MEDIA_SIZE 解析失败: {e}，使用默认值")
        return 2000.0 * 1024 * 1024


async def get_media_size(media):
    """获取媒体文件大小"""
    if not media:
        return 0

    try:
        # 对于所有类型的媒体，先尝试获取 document
        if hasattr(media, "document") and media.document:
            return media.document.size

        # 对于照片，获取最大尺寸
        if hasattr(media, "photo") and media.photo:
            # 获取最大尺寸的照片
            largest_photo = max(
                media.photo.sizes, key=lambda x: x.size if hasattr(x, "size") else 0
            )
            return largest_photo.size if hasattr(largest_photo, "size") else 0

        # 如果是其他类型，尝试直接获取 size 属性
        if hasattr(media, "size"):
            return media.size

    except Exception as e:
        logger.error(f"获取媒体大小时出错: {str(e)}")

    return 0


async def get_max_media_size():
    """获取媒体文件大小上限（带缓存）"""
    global _CACHED_MAX_SIZE
    if _CACHED_MAX_SIZE is None:
        _CACHED_MAX_SIZE = _load_max_size()
    return _CACHED_MAX_SIZE


async def download_media_with_retry(client, media, file, retries=3):
    """带重试机制的媒体下载"""
    import asyncio
    
    for i in range(retries):
        try:
            return await client.download_media(media, file=file)
        except Exception as e:
            if i == retries - 1:
                logger.error(f"下载失败 (尝试 {i+1}/{retries}): {e}")
                raise e
            logger.warning(f"下载重试 ({i+1}/{retries}): {e}")
            await asyncio.sleep(2 * (i + 1))
