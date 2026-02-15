"""
实时统计数据缓存管理
确保菜单页面显示的统计数据及时更新
"""

import weakref
from datetime import datetime, timedelta

import asyncio
import logging
from typing import Any, Dict, Optional, Callable, cast, List

logger = logging.getLogger(__name__)


class RealtimeStatsCache:
    """实时统计数据缓存"""

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = {
            "forward_stats": 30,  # 转发统计缓存30秒
            "dedup_stats": 60,  # 去重统计缓存1分钟
            "system_stats": 120,  # 系统统计缓存2分钟
            "rule_stats": 300,  # 规则统计缓存5分钟
        }
        self._update_callbacks: weakref.WeakSet[Callable[..., Any]] = weakref.WeakSet()

    def register_update_callback(self, callback: Callable[..., Any]) -> None:
        """注册数据更新回调"""
        self._update_callbacks.add(callback)

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否仍然有效"""
        if key not in self._cache_time:
            return False

        ttl = self._cache_ttl.get(key, 60)
        elapsed = (datetime.now() - self._cache_time[key]).total_seconds()
        return elapsed < ttl

    async def get_forward_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """获取转发统计数据"""
        cache_key = "forward_stats"

        if not force_refresh and self._is_cache_valid(cache_key):
            return cast(Dict[str, Any], self._cache[cache_key])

        try:
            mod = __import__('services.forward_service', fromlist=['forward_service'])
            forward_service = mod.forward_service

            stats = await forward_service.get_forward_stats()

            # 更新缓存
            self._cache[cache_key] = stats
            self._cache_time[cache_key] = datetime.now()

            # 通知更新
            await self._notify_update("forward_stats", stats)

            return cast(Dict[str, Any], stats)

        except Exception as e:
            logger.error(f"获取转发统计失败: {e}")
            return cast(Dict[str, Any], self._cache.get(
                cache_key,
                {
                    "today": {
                        "total_forwards": 0,
                        "total_size_bytes": 0,
                        "active_chats": 0,
                    },
                    "trend": {"percentage": 0, "direction": "unknown"},
                },
            ))

    async def get_dedup_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """获取去重统计数据"""
        cache_key = "dedup_stats"

        if not force_refresh and self._is_cache_valid(cache_key):
            return cast(Dict[str, Any], self._cache[cache_key])

        try:
            mod = __import__('services.dedup_service', fromlist=['dedup_service'])
            dedup_service = mod.dedup_service

            stats = await dedup_service.get_dedup_config()

            # 更新缓存
            self._cache[cache_key] = stats
            self._cache_time[cache_key] = datetime.now()

            # 通知更新
            await self._notify_update("dedup_stats", stats)

            return cast(Dict[str, Any], stats)

        except Exception as e:
            logger.error(f"获取去重统计失败: {e}")
            return cast(Dict[str, Any], self._cache.get(
                cache_key,
                {
                    "stats": {
                        "cached_signatures": 0,
                        "cached_content_hashes": 0,
                        "tracked_chats": 0,
                    },
                    "enabled_features": [],
                },
            ))

    async def get_system_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """获取系统统计数据"""
        cache_key = "system_stats"

        if not force_refresh and self._is_cache_valid(cache_key):
            return cast(Dict[str, Any], self._cache[cache_key])

        try:
            mod = __import__('services.analytics_service', fromlist=['analytics_service'])
            analytics_service = mod.analytics_service

            stats = await analytics_service.get_system_status()

            # 更新缓存
            self._cache[cache_key] = stats
            self._cache_time[cache_key] = datetime.now()

            # 通知更新
            await self._notify_update("system_stats", stats)

            return cast(Dict[str, Any], stats)

        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return cast(Dict[str, Any], self._cache.get(
                cache_key,
                {
                    "system_resources": {
                        "cpu_percent": 0,
                        "memory_percent": 0,
                        "status": "unknown",
                    },
                    "overall_status": "unknown",
                },
            ))

    async def invalidate_cache(self, key: Optional[str] = None) -> None:
        """使缓存失效"""
        if key:
            self._cache.pop(key, None)
            self._cache_time.pop(key, None)
            logger.info(f"缓存已失效: {key}")
        else:
            self._cache.clear()
            self._cache_time.clear()
            logger.info("所有缓存已清空")

    async def _notify_update(self, data_type: str, data: Dict[str, Any]) -> None:
        """通知所有注册的回调数据已更新"""
        for callback in list(self._update_callbacks):
            try:
                await callback(data_type, data)
            except Exception as e:
                logger.error(f"数据更新回调失败: {e}")

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        info = {}
        for key in self._cache_time:
            age = (datetime.now() - self._cache_time[key]).total_seconds()
            ttl = self._cache_ttl.get(key, 60)
            info[key] = {
                "age_seconds": age,
                "ttl_seconds": ttl,
                "valid": age < ttl,
                "size_bytes": len(str(self._cache.get(key, {}))),
            }
        return info


# 全局实时统计缓存实例
realtime_stats_cache = RealtimeStatsCache()


async def get_main_menu_stats(force_refresh: bool = False) -> Dict[str, Any]:
    """获取主菜单所需的统计数据（组合接口）"""
    try:
        # 并行获取所有统计数据
        results: List[Any] = await asyncio.gather(
            realtime_stats_cache.get_forward_stats(force_refresh),
            realtime_stats_cache.get_dedup_stats(force_refresh),
            return_exceptions=True,
        )
        forward_stats, dedup_stats = results[0], results[1]

        # 处理异常情况
        if isinstance(forward_stats, Exception):
            logger.error(f"获取转发统计异常: {forward_stats}")
            forward_stats = {"today": {"total_forwards": 0, "total_size_bytes": 0}}

        if isinstance(dedup_stats, Exception):
            logger.error(f"获取去重统计异常: {dedup_stats}")
            dedup_stats = {"stats": {"cached_signatures": 0}}

        return {
            "today": forward_stats.get("today", {}),
            "dedup": dedup_stats.get("stats", {}),
            "trend": forward_stats.get("trend", {}),
            "last_updated": datetime.now().strftime("%H:%M:%S"),
        }

    except Exception as e:
        logger.error(f"获取主菜单统计失败: {e}")
        return {
            "today": {"total_forwards": 0, "total_size_bytes": 0, "active_chats": 0},
            "dedup": {"cached_signatures": 0, "cached_content_hashes": 0},
            "trend": {"percentage": 0, "direction": "unknown"},
            "last_updated": datetime.now().strftime("%H:%M:%S"),
            "error": str(e),
        }
