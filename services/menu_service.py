"""
菜单业务逻辑服务
从 MenuController 剥离出的业务逻辑，负责数据聚合与状态管理
"""
import logging
from typing import Dict, Any
from services.analytics_service import analytics_service

logger = logging.getLogger(__name__)

class MenuService:
    def __init__(self):
        from core.container import container
        self.container = container

    async def get_main_menu_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """获取主菜单展示数据"""
        from core.helpers.realtime_stats import get_main_menu_stats
        return await get_main_menu_stats(force_refresh=force_refresh)

    async def get_forward_hub_data(self) -> Dict[str, Any]:
        """获取转发中心展示数据"""
        from core.helpers.realtime_stats import realtime_stats_cache
        stats = await realtime_stats_cache.get_forward_stats()
        return {'overview': stats.get('today', {})}

    async def get_dedup_hub_data(self) -> Dict[str, Any]:
        """获取去重中心展示数据"""
        from core.helpers.realtime_stats import realtime_stats_cache
        return await realtime_stats_cache.get_dedup_stats()

    async def get_system_hub_data(self) -> Dict[str, Any]:
        """获取系统设置中心展示数据"""
        from core.helpers.realtime_stats import realtime_stats_cache
        return await realtime_stats_cache.get_system_stats()

    async def get_analytics_hub_data(self) -> Dict[str, Any]:
        """获取数据分析中心展示数据"""
        return await analytics_service.get_analytics_overview()

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """获取实时监控指标"""
        metrics = await analytics_service.get_performance_metrics()
        status = await analytics_service.get_system_status()
        return {
            'metrics': metrics,
            'status': status
        }

menu_service = MenuService()
