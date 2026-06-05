"""
数据分析菜单模块
处理统计概览、详细分析、性能监控、异常检测及报告导出
"""
import logging
from datetime import datetime, timedelta
from telethon import Button
from ..base import BaseMenu
from services.analytics_service import analytics_service

logger = logging.getLogger(__name__)

class AnalyticsMenu(BaseMenu):
    """数据分析菜单"""

    async def show_forward_analytics(self, event):
        """显示转发分析面板"""
        from controllers.menu_controller import menu_controller
        await menu_controller.show_forward_analytics(event)

    async def _calculate_system_health(self, stats: dict) -> float:
        score = 100.0
        total = stats.get("total_forwards", 0)
        if total == 0: score -= 30
        elif total > 1000: score += 10
        if len(stats.get("types", {})) > 5: score += 5
        elif len(stats.get("types", {})) < 2: score -= 10
        return max(0, min(100, score))

    async def show_detailed_analytics(self, event):
        """详细分析（最近7天）"""
        from controllers.menu_controller import menu_controller
        await menu_controller.show_detailed_analytics(event)

    async def show_performance_analysis(self, event):
        """性能分析"""
        from controllers.menu_controller import menu_controller
        await menu_controller.show_performance_analysis(event)

    async def show_anomaly_detection(self, event):
        """显示异常检测结果"""
        from controllers.menu_controller import menu_controller
        await menu_controller.run_anomaly_detection(event)

    async def show_failure_analysis(self, event):
        """失败分析与错误报告"""
        from controllers.menu_controller import menu_controller
        await menu_controller.show_failure_analysis(event)

    async def export_report(self, event):
        """导出报告"""
        from controllers.menu_controller import menu_controller
        await menu_controller.export_analytics_csv(event)

analytics_menu = AnalyticsMenu()
