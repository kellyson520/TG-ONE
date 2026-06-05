from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry

@MenuHandlerRegistry.register
class AnalyticsMenuStrategy(BaseMenuHandler):
    """
    Handles Analytics and Data Analysis actions:
    - Forward Analytics
    - Realtime Monitor  
    - Anomaly Detection
    - Performance Analysis
    - DB Performance Monitor
    - DB Optimization Center
    - Detailed Reports
    - CSV Export
    """

    ACTIONS = {
        "forward_analytics", "realtime_monitor", "anomaly_detection",
        "performance_analysis", "db_performance_monitor", "db_optimization_center",
        "detailed_analytics", "export_csv",
        "db_query_analysis", "db_performance_trends", "db_alert_management",
        "db_optimization_advice", "db_detailed_report", "db_optimization_config",
        "db_index_analysis", "db_cache_management", "db_optimization_logs",
        "enable_db_optimization", "run_db_optimization_check",
        "refresh_db_performance", "refresh_db_optimization_status",
        "run_db_reindex", "clear_db_alerts"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller

        # 1. Analytics Overview
        if action == "forward_analytics":
            await menu_controller.show_forward_analytics(event)
        
        elif action == "realtime_monitor":
            await menu_controller.show_realtime_monitor(event)
        
        elif action == "anomaly_detection":
            await menu_controller.run_anomaly_detection(event)
        
        elif action == "performance_analysis":
            await menu_controller.show_performance_analysis(event)
        
        elif action == "detailed_analytics":
            await menu_controller.show_detailed_analytics(event)
        
        elif action == "export_csv":
            await menu_controller.export_analytics_csv(event)
        
        # 2. DB Performance
        elif action == "db_performance_monitor":
            await menu_controller.show_db_performance_monitor(event)
        
        elif action == "db_optimization_center":
            await menu_controller.show_db_optimization_center(event)
        
        elif action == "db_query_analysis":
            await menu_controller.show_db_query_analysis(event)
        
        elif action == "db_performance_trends":
            await menu_controller.show_db_performance_trends(event)
        
        elif action == "db_alert_management":
            await menu_controller.show_db_alert_management(event)
        
        elif action == "db_optimization_advice":
            await menu_controller.show_db_optimization_advice(event)
        
        elif action == "db_detailed_report":
            await menu_controller.show_db_detailed_report(event)
        
        elif action == "db_optimization_config":
            await menu_controller.show_db_optimization_config(event)
        
        elif action == "db_index_analysis":
            await menu_controller.show_db_index_analysis(event)
        
        elif action == "db_cache_management":
            await menu_controller.show_db_cache_management(event)
        
        elif action == "db_optimization_logs":
            await menu_controller.show_db_optimization_logs(event)
        
        # 3. DB Operations
        elif action == "enable_db_optimization":
            await menu_controller.enable_db_optimization(event)
        
        elif action == "run_db_optimization_check":
            await menu_controller.run_db_optimization_check(event)
        
        elif action == "refresh_db_performance":
            await menu_controller.refresh_db_performance(event)
        
        elif action == "refresh_db_optimization_status":
            await menu_controller.refresh_db_optimization_status(event)
        
        elif action == "run_db_reindex":
            await menu_controller.run_db_reindex(event)
        
        elif action == "clear_db_alerts":
            await menu_controller.clear_db_alerts(event)
