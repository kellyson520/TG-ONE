"""
统一缓存优化系统
整合内存缓存、持久化缓存和智能缓存策略，提供高性能的缓存解决方案
"""

import functools
import hashlib
import threading
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

import asyncio
import json
import time
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from utils.core.error_handler import handle_errors
from utils.core.logger_utils import get_logger, log_performance
from repositories.persistent_cache import get_persistent_cache


# 实现一个简单的TTLCache类作为临时解决方案
class TTLCache:
    def __init__(self, ttl_seconds, maxsize):
        self.ttl_seconds = ttl_seconds
        self.maxsize = maxsize
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value):
        self._store[key] = value
        # 简单的大小限制
        if len(self._store) > self.maxsize:
            # 移除最早的条目
            for k in list(self._store.keys())[: len(self._store) - self.maxsize]:
                del self._store[k]

    def delete(self, key):
        if key in self._store:
            del self._store[key]

    def clear(self):
        self._store.clear()


T = TypeVar("T")
logger = get_logger(__name__)


@dataclass
class CacheStats:
    """缓存统计信息"""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class CacheKey:
    """缓存键生成器"""

    @staticmethod
    def generate(prefix: str, *args, **kwargs) -> str:
        """
        生成缓存键

        Args:
            prefix: 键前缀
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            生成的缓存键
        """
        # 创建参数的哈希值
        key_data = {"args": args, "kwargs": kwargs}

        key_json = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()[:16]  # 降低碰撞风险

        return f"{prefix}:{key_hash}"

    @staticmethod
    def generate_for_function(func: Callable, *args, **kwargs) -> str:
        """
        为函数生成缓存键

        Args:
            func: 函数对象
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            生成的缓存键
        """
        func_name = f"{func.__module__}.{func.__name__}"
        return CacheKey.generate(func_name, *args, **kwargs)


class MultiLevelCache(Generic[T]):
    """多级缓存系统"""

    def __init__(
        self,
        name: str,
        l1_ttl: int = 300,  # L1缓存TTL（5分钟）
        l1_maxsize: int = 1000,  # L1缓存最大条目数
        l2_ttl: int = 3600,  # L2缓存TTL（1小时）
        enable_persistent: bool = True,
    ):  # 是否启用持久化
        """
        初始化多级缓存

        Args:
            name: 缓存名称
            l1_ttl: L1缓存生存时间（秒）
            l1_maxsize: L1缓存最大条目数
            l2_ttl: L2缓存生存时间（秒）
            enable_persistent: 是否启用持久化缓存
        """
        self.name = name
        self.l1_ttl = l1_ttl
        self.l2_ttl = l2_ttl

        # L1: 内存缓存（最快）
        self.l1_cache = TTLCache(ttl_seconds=l1_ttl, maxsize=l1_maxsize)

        # L2: 持久化缓存（Redis/SQLite）
        self.l2_cache = get_persistent_cache() if enable_persistent else None

        # 统计信息
        self.stats = CacheStats()
        self._lock = threading.RLock()

        logger.log_system_state(
            f"多级缓存-{name}",
            "初始化完成",
            {
                "l1_ttl": l1_ttl,
                "l1_maxsize": l1_maxsize,
                "l2_ttl": l2_ttl,
                "enable_persistent": enable_persistent,
            },
        )

    @handle_errors(default_return=None)
    def get(self, key: str) -> Optional[T]:
        """
        获取缓存值（多级查找）

        Args:
            key: 缓存键

        Returns:
            缓存值或None
        """
        with self._lock:
            # L1缓存查找
            value = self.l1_cache.get(key)
            if value is not None:
                self.stats.hits += 1
                logger.log_data_flow(f"L1缓存命中-{self.name}", 1, "条目", {"key": key})
                return value

            # L2缓存查找
            if self.l2_cache:
                try:
                    l2_value = self.l2_cache.get(key)
                    if l2_value is not None:
                        # 反序列化
                        value = json.loads(l2_value)

                        # 回填到L1缓存
                        self.l1_cache.set(key, value)

                        self.stats.hits += 1
                        logger.log_data_flow(
                            f"L2缓存命中-{self.name}", 1, "条目", {"key": key}
                        )
                        return value
                except Exception as e:
                    logger.log_error(f"L2缓存读取-{self.name}", e, context={"key": key})

            self.stats.misses += 1
            return None

    @handle_errors(default_return=False)
    def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        """
        设置缓存值（多级存储）

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（可选，使用默认值）

        Returns:
            是否设置成功
        """
        with self._lock:
            try:
                # L1缓存存储
                self.l1_cache.set(key, value)

                # L2缓存存储
                if self.l2_cache:
                    try:
                        # 序列化值
                        serialized_value = json.dumps(value, default=str)
                        self.l2_cache.set(key, serialized_value, ttl or self.l2_ttl)
                    except Exception as e:
                        logger.log_error(
                            f"L2缓存写入-{self.name}", e, context={"key": key}
                        )

                self.stats.sets += 1
                self.stats.size = len(self.l1_cache._store)

                logger.log_data_flow(f"缓存存储-{self.name}", 1, "条目", {"key": key})
                return True

            except Exception as e:
                logger.log_error(f"缓存存储-{self.name}", e, context={"key": key})
                return False

    @handle_errors(default_return=False)
    def delete(self, key: str) -> bool:
        """
        删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        with self._lock:
            try:
                # L1缓存删除
                self.l1_cache.delete(key)

                # L2缓存删除
                if self.l2_cache:
                    try:
                        self.l2_cache.delete(key)
                    except Exception as e:
                        logger.log_error(
                            f"L2缓存删除-{self.name}", e, context={"key": key}
                        )

                self.stats.deletes += 1
                self.stats.size = len(self.l1_cache._store)

                logger.log_data_flow(f"缓存删除-{self.name}", 1, "条目", {"key": key})
                return True

            except Exception as e:
                logger.log_error(f"缓存删除-{self.name}", e, context={"key": key})
                return False

    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self.l1_cache.clear()
            if self.l2_cache:
                try:
                    self.l2_cache.clear()
                except Exception as e:
                    logger.log_error(f"L2缓存清空-{self.name}", e)

            old_stats = self.stats
            self.stats = CacheStats()

            logger.log_system_state(
                f"缓存清空-{self.name}", "完成", old_stats.to_dict()
            )

    def get_stats(self) -> CacheStats:
        """获取缓存统计信息"""
        with self._lock:
            self.stats.size = len(self.l1_cache._store)
            return self.stats


class SmartCache:
    """智能缓存管理器"""

    def __init__(self):
        """初始化智能缓存管理器"""
        self.caches: Dict[str, MultiLevelCache] = {}
        self.access_patterns: Dict[str, List[float]] = defaultdict(list)
        self.auto_optimization = True

        logger.log_system_state("智能缓存管理器", "初始化完成")

    def get_cache(self, name: str, **cache_config) -> MultiLevelCache:
        """
        获取或创建缓存实例

        Args:
            name: 缓存名称
            **cache_config: 缓存配置参数

        Returns:
            多级缓存实例
        """
        if name not in self.caches:
            self.caches[name] = MultiLevelCache(name, **cache_config)
            logger.log_system_state(f"缓存创建-{name}", "完成", cache_config)

        return self.caches[name]

    def record_access(self, cache_name: str) -> None:
        """记录缓存访问模式"""
        if self.auto_optimization:
            self.access_patterns[cache_name].append(time.time())

            # 保持最近100次访问记录
            if len(self.access_patterns[cache_name]) > 100:
                self.access_patterns[cache_name] = self.access_patterns[cache_name][
                    -100:
                ]

    def analyze_patterns(self, cache_name: str) -> Dict[str, Any]:
        """
        分析缓存访问模式

        Args:
            cache_name: 缓存名称

        Returns:
            访问模式分析结果
        """
        if cache_name not in self.access_patterns:
            return {}

        accesses = self.access_patterns[cache_name]
        if len(accesses) < 2:
            return {}

        now = time.time()
        recent_accesses = [t for t in accesses if now - t < 3600]  # 最近1小时

        if len(recent_accesses) < 2:
            return {}

        # 计算访问频率
        time_span = recent_accesses[-1] - recent_accesses[0]
        frequency = len(recent_accesses) / time_span if time_span > 0 else 0

        # 计算访问间隔
        intervals = [
            recent_accesses[i] - recent_accesses[i - 1]
            for i in range(1, len(recent_accesses))
        ]
        avg_interval = sum(intervals) / len(intervals) if intervals else 0

        return {
            "frequency_per_second": frequency,
            "average_interval_seconds": avg_interval,
            "recent_access_count": len(recent_accesses),
            "time_span_seconds": time_span,
        }

    def optimize_cache_config(self, cache_name: str) -> Dict[str, Any]:
        """
        基于访问模式优化缓存配置

        Args:
            cache_name: 缓存名称

        Returns:
            建议的缓存配置
        """
        patterns = self.analyze_patterns(cache_name)
        if not patterns:
            return {}

        frequency = patterns.get("frequency_per_second", 0)
        avg_interval = patterns.get("average_interval_seconds", 300)

        # 基于访问频率调整配置
        if frequency > 1:  # 高频访问
            suggested_config = {
                "l1_ttl": min(int(avg_interval * 3), 1800),  # 3倍间隔，最多30分钟
                "l1_maxsize": 2000,
                "l2_ttl": 7200,  # 2小时
            }
        elif frequency > 0.1:  # 中频访问
            suggested_config = {
                "l1_ttl": min(int(avg_interval * 2), 900),  # 2倍间隔，最多15分钟
                "l1_maxsize": 1000,
                "l2_ttl": 3600,  # 1小时
            }
        else:  # 低频访问
            suggested_config = {
                "l1_ttl": min(int(avg_interval), 300),  # 1倍间隔，最多5分钟
                "l1_maxsize": 500,
                "l2_ttl": 1800,  # 30分钟
            }

        logger.log_operation(
            f"缓存配置优化-{cache_name}",
            details=f"模式: {patterns}, 建议: {suggested_config}",
        )

        return suggested_config

    def get_global_stats(self) -> Dict[str, Any]:
        """获取全局缓存统计信息"""
        global_stats = {"total_caches": len(self.caches), "caches": {}}

        total_hits = 0
        total_misses = 0
        total_size = 0

        for name, cache in self.caches.items():
            stats = cache.get_stats()
            cache_stats = stats.to_dict()
            cache_stats["patterns"] = self.analyze_patterns(name)

            global_stats["caches"][name] = cache_stats

            total_hits += stats.hits
            total_misses += stats.misses
            total_size += stats.size

        global_stats.update(
            {
                "total_hits": total_hits,
                "total_misses": total_misses,
                "total_size": total_size,
                "global_hit_rate": (
                    total_hits / (total_hits + total_misses)
                    if (total_hits + total_misses) > 0
                    else 0.0
                ),
            }
        )

        return global_stats


# 全局智能缓存管理器实例 - 延迟初始化
smart_cache = None


def _init_smart_cache():
    """延迟初始化智能缓存管理器"""
    global smart_cache
    if smart_cache is None:
        smart_cache = SmartCache()


def get_smart_cache(name: str, **config) -> MultiLevelCache:
    """
    获取智能缓存实例

    Args:
        name: 缓存名称
        **config: 缓存配置

    Returns:
        多级缓存实例
    """
    _init_smart_cache()
    cache = smart_cache.get_cache(name, **config)
    smart_cache.record_access(name)
    return cache


# 缓存装饰器
def cached(cache_name: str = None, ttl: int = 300, key_func: Optional[Callable] = None):
    """
    缓存装饰器

    Args:
        cache_name: 缓存名称（默认使用函数名）
        ttl: 缓存生存时间
        key_func: 自定义键生成函数
    """

    def decorator(func):
        nonlocal cache_name
        if cache_name is None:
            cache_name = f"{func.__module__}.{func.__name__}"

        # 延迟获取缓存实例，确保在setup_logging()之后初始化
        def get_cache():
            return get_smart_cache(cache_name, l1_ttl=ttl, l2_ttl=ttl * 2)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache()
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = CacheKey.generate_for_function(func, *args, **kwargs)

            # 尝试从缓存获取
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.log_operation(
                    f"缓存命中-{cache_name}", details=f"键: {cache_key}"
                )
                return cached_result

            # 执行原函数
            start_time = time.time()
            result = await func(*args, **kwargs)
            duration = time.time() - start_time

            # 存储到缓存
            cache.set(cache_key, result, ttl)

            logger.log_performance(
                f"缓存写入-{cache_name}",
                duration,
                details=f"键: {cache_key}, 结果大小: {len(str(result))}",
            )

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache = get_cache()
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = CacheKey.generate_for_function(func, *args, **kwargs)

            # 尝试从缓存获取
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.log_operation(
                    f"缓存命中-{cache_name}", details=f"键: {cache_key}"
                )
                return cached_result

            # 执行原函数
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            # 存储到缓存
            cache.set(cache_key, result, ttl)

            logger.log_performance(
                f"缓存写入-{cache_name}",
                duration,
                details=f"键: {cache_key}, 结果大小: {len(str(result))}",
            )

            return result

        # 根据函数类型返回对应的包装器
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# 缓存预热功能
class CacheWarmer:
    """缓存预热器"""

    def __init__(self, cache: MultiLevelCache):
        """
        初始化缓存预热器

        Args:
            cache: 缓存实例
        """
        self.cache = cache
        self.logger = get_logger(f"{__name__}.CacheWarmer")

    @log_performance("缓存预热")
    async def warm_up(
        self,
        data_loader: Callable,
        keys: List[str],
        batch_size: int = 10,
        delay: float = 0.1,
    ) -> Dict[str, Any]:
        """
        执行缓存预热

        Args:
            data_loader: 数据加载函数
            keys: 要预热的键列表
            batch_size: 批处理大小
            delay: 批次间延迟

        Returns:
            预热结果统计
        """
        total_keys = len(keys)
        successful = 0
        failed = 0

        self.logger.log_operation("缓存预热开始", details=f"总键数: {total_keys}")

        for i in range(0, total_keys, batch_size):
            batch_keys = keys[i : i + batch_size]

            for key in batch_keys:
                try:
                    if self.cache.get(key) is None:  # 只预热未缓存的数据
                        data = (
                            await data_loader(key)
                            if asyncio.iscoroutinefunction(data_loader)
                            else data_loader(key)
                        )
                        if data is not None:
                            self.cache.set(key, data)
                            successful += 1
                        else:
                            failed += 1
                    else:
                        # 已存在缓存，跳过
                        pass
                except Exception as e:
                    self.logger.log_error("缓存预热", e, context={"key": key})
                    failed += 1

            # 批次间延迟
            if i + batch_size < total_keys:
                await asyncio.sleep(delay)

        result = {
            "total_keys": total_keys,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total_keys if total_keys > 0 else 0.0,
        }

        self.logger.log_operation("缓存预热完成", details=str(result))
        return result


# 便捷函数
def create_cache_warmer(cache_name: str) -> CacheWarmer:
    """创建缓存预热器"""
    cache = get_smart_cache(cache_name)
    return CacheWarmer(cache)


def get_cache_stats(cache_name: str = None) -> Dict[str, Any]:
    """获取缓存统计信息"""
    _init_smart_cache()
    if cache_name:
        if cache_name in smart_cache.caches:
            return smart_cache.caches[cache_name].get_stats().to_dict()
        else:
            return {}
    else:
        return smart_cache.get_global_stats()


def optimize_all_caches() -> Dict[str, Any]:
    """优化所有缓存配置"""
    _init_smart_cache()
    optimization_results = {}

    for cache_name in smart_cache.caches.keys():
        suggested_config = smart_cache.optimize_cache_config(cache_name)
        optimization_results[cache_name] = suggested_config

    logger.log_operation("全局缓存优化", details=f"优化结果: {optimization_results}")
    return optimization_results
