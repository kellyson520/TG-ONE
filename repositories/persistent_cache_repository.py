import asyncio
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def get_persistent_cache():
    """Lazy-load the shared persistent cache backend."""
    from core.cache.persistent_cache import get_persistent_cache as factory

    return factory()


class PersistentCacheRepository:
    """
    持久化缓存仓库.

    Dedup PCache is best-effort: backend failures degrade to misses/write
    failures and must not change the dedup decision path.
    """

    def __init__(self, cache: Optional[Any] = None):
        self._cache = cache

    @property
    def cache(self):
        if self._cache is None:
            self._cache = get_persistent_cache()
        return self._cache

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            return await asyncio.to_thread(self.cache.get, key)
        except Exception as exc:
            logger.debug("PCache读取失败 (%s): %s", key, exc)
            return None

    async def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存值"""
        try:
            await asyncio.to_thread(self.cache.set, key, value, ttl=expire)
            return True
        except Exception as exc:
            logger.debug("PCache写入失败 (%s): %s", key, exc)
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        try:
            await asyncio.to_thread(self.cache.delete, key)
            return True
        except Exception as exc:
            logger.debug("PCache删除失败 (%s): %s", key, exc)
            return False
