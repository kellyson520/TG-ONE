import asyncio
from typing import Any, Callable, Dict, Optional, TypeVar

from core.cache.unified_cache import get_smart_cache, MultiLevelCache
from core.logging import get_logger

logger = get_logger(__name__)
T = TypeVar("T")

class CacheService:
    """
    统一缓存服务 (Unified Cache Service)
    
    特性:
    1. 集成 MultiLevelCache (L1内存 + L2持久化)
    2. 防击穿逻辑 (Anti-Stampede / Thundering Herd Protection)
    3. 异步非阻塞设计 (Offload blocking L2 I/O to threads)
    """
    
    _instance: Optional["CacheService"] = None
    
    def __init__(self):
        self._cache_map: Dict[str, MultiLevelCache] = {}
        self._locks: Dict[str, asyncio.Lock] = {} 
        self._lock_maxsize = 5000
        self._lock_creation_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "CacheService":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    def _get_cache(self, name: str = "default") -> MultiLevelCache:
        """获取或创建底层缓存实例"""
        if name not in self._cache_map:
            # 默认配置: L1=5分钟, L2=1小时
            self._cache_map[name] = get_smart_cache(name, l1_ttl=300, l2_ttl=3600)
        return self._cache_map[name]

    async def _safe_cache_get(
        self, cache: MultiLevelCache, key: str, cache_name: str
    ) -> Any:
        try:
            return await asyncio.to_thread(cache.get, key)
        except Exception as e:
            logger.warning(
                "Cache get failed cache=%s key=%r: %s",
                cache_name,
                key,
                e,
            )
            return None

    async def _safe_cache_set(
        self,
        cache: MultiLevelCache,
        key: str,
        value: Any,
        ttl: int,
        cache_name: str,
    ) -> None:
        try:
            await asyncio.to_thread(cache.set, key, value, ttl)
        except Exception as e:
            logger.warning(
                "Cache set failed cache=%s key=%r: %s",
                cache_name,
                key,
                e,
            )

    async def _safe_cache_delete(
        self, cache: MultiLevelCache, key: str, cache_name: str
    ) -> None:
        try:
            await asyncio.to_thread(cache.delete, key)
        except Exception as e:
            logger.warning(
                "Cache delete failed cache=%s key=%r: %s",
                cache_name,
                key,
                e,
            )

    async def _safe_cache_clear(
        self, cache: MultiLevelCache, cache_name: str
    ) -> None:
        try:
            await asyncio.to_thread(cache.clear)
        except Exception as e:
            logger.warning(
                "Cache clear failed cache=%s: %s",
                cache_name,
                e,
            )

    async def _get_lock(self, key: str) -> asyncio.Lock:
        """获取用于防击穿的锁"""
        if key not in self._locks:
            async with self._lock_creation_lock:
                if key not in self._locks:
                    if len(self._locks) >= self._lock_maxsize:
                        for old_key, old_lock in list(self._locks.items()):
                            if not old_lock.locked():
                                self._locks.pop(old_key, None)
                                if len(self._locks) < self._lock_maxsize:
                                    break
                    self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def get(self, key: str, cache_name: str = "default") -> Any:
        """异步获取缓存值"""
        cache = self._get_cache(cache_name)
        # 将潜在的阻塞 L2 读取放入线程池
        return await self._safe_cache_get(cache, key, cache_name)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
        cache_name: str = "default",
    ):
        """异步设置缓存值"""
        cache = self._get_cache(cache_name)
        await self._safe_cache_set(cache, key, value, ttl, cache_name)

    async def delete(self, key: str, cache_name: str = "default"):
        """异步删除缓存值"""
        cache = self._get_cache(cache_name)
        await self._safe_cache_delete(cache, key, cache_name)

    async def clear(self, cache_name: str = "default"):
        """异步清空缓存"""
        cache = self._get_cache(cache_name)
        await self._safe_cache_clear(cache, cache_name)
        
    async def get_or_compute(
        self, 
        key: str, 
        factory: Callable[[], Any], 
        ttl: int = 300, 
        cache_name: str = "default"
    ) -> Any:
        """
        获取缓存，如果不存在则计算并回填。
        包含防击穿 (Anti-Stampede) 逻辑：
        当缓存失效时，只有一个请求会执行 factory，其他请求等待结果。
        """
        cache = self._get_cache(cache_name)
        
        # 1. 快速检查 (Fast Path) - 尝试直接读取
        # 这里先尝试非阻塞读 (如果 L1 命中则很快)
        # 为简单起见，统一用 to_thread，或者假设 L1 get 极快可以直接调用？
        # MultiLevelCache.get 若 L1 Miss 会查 L2 (Blocking)。
        # 所以第一次 check 也应该是 async 的。
        val = await self._safe_cache_get(cache, key, cache_name)
        if val is not None:
            return val
            
        # 2. 获取锁 (Slow Path)
        lock = await self._get_lock(key)
        
        async with lock:
            # 3. 双重检查 (Double Check)
            val = await self._safe_cache_get(cache, key, cache_name)
            if val is not None:
                return val
            
            # 4. 执行计算 (Execute Factory)
            try:
                if asyncio.iscoroutinefunction(factory):
                    val = await factory()
                else:
                    val = await asyncio.to_thread(factory)
                
                # 5. 回填缓存
                if val is not None:
                    await self._safe_cache_set(cache, key, val, ttl, cache_name)
                
                return val
            except Exception as e:
                logger.error(
                    "Error computing value for cache key '%s': %s",
                    key,
                    e,
                    exc_info=True,
                )
                raise

    # 装饰器支持
    @classmethod
    def cached(cls, cache_name: str = "default", ttl: int = 300):
        """
        Service 方法装饰器
        @CacheService.cached(cache_name="user_data", ttl=600)
        async def get_user_data(user_id):
            ...
        """
        def decorator(func):
            import functools
            from core.cache.unified_cache import CacheKey
            
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # 生成唯一 Key
                key = CacheKey.generate_for_function(func, *args, **kwargs)
                service = cls.get_instance()
                
                # 构造 factory
                async def factory():
                    return await func(*args, **kwargs)
                
                return await service.get_or_compute(key, factory, ttl, cache_name)
            return wrapper
        return decorator

# 全局实例
cache_service = CacheService.get_instance()
