from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from core.container import container
from telethon import Button
# Lazy import to avoid potential circular dependency issues during module loading
# from controllers.menu_controller import menu_controller
# from handlers.button.new_menu_system import new_menu_system

@MenuHandlerRegistry.register
class SystemMenuStrategy(BaseMenuHandler):
    """
    Handles System-level menu actions:
    - Main Menu
    - Forward Hub, Dedup Hub, Analytics Hub, System Hub
    - Help, Docs, FAQ, Support
    - Backup & Restore
    - Cache Cleanup, System Overview
    - Search
    - Exit/Close
    """

    ACTIONS = {
        "main_menu", "main", "main_menu_refresh", "refresh_main_menu",
        "forward_hub", "refresh_forward_hub",
        "dedup_hub", "analytics_hub", "system_hub",
        "help_guide", "detailed_docs", "faq", "tech_support",
        "exit", "close", "forward_search", "system_settings",
        "db_backup", "backup_current", "do_backup",
        "view_backups", "backup_page",
        "restore_backup", "do_restore",
        "system_overview",
        "cache_cleanup", "do_cleanup",
        "log_viewer", "system_status", "system_logs",
        "db_archive_once", "session_management",
        "db_optimization_center", "db_performance_monitor",
        "refresh_db_performance", "db_query_analysis",
        "db_performance_trends", "db_alert_management",
        "run_db_optimization_check", "db_reindex",
        "db_archive_center", "db_optimization_config",
        "clear_dedup_cache"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        from handlers.button.new_menu_system import new_menu_system

        extra_data = kwargs.get("extra_data", [])

        # 1. Main Navigation
        if action in ["main_menu", "main"]:
            await menu_controller.show_main_menu(event)
        
        elif action == "main_menu_refresh":
            await menu_controller.show_main_menu(event, force_refresh=True)
            await event.answer("✅ 数据看板已刷新")

        elif action == "forward_hub":
            await menu_controller.show_forward_hub(event)
        
        elif action == "refresh_forward_hub":
            await menu_controller.show_forward_hub(event, force_refresh=True)
            await event.answer("✅ 转发中心已刷新")

        elif action == "dedup_hub":
            await menu_controller.show_dedup_hub(event)
        
        elif action == "analytics_hub":
            await menu_controller.show_analytics_hub(event)
        
        elif action == "system_hub":
            await menu_controller.show_system_hub(event)

        # 2. Help & Support
        elif action == "help_guide":
            await menu_controller.show_help_guide(event)
        
        elif action == "detailed_docs":
            await menu_controller.show_detailed_docs(event)
        
        elif action == "faq":
            await menu_controller.show_faq(event)
        
        elif action == "tech_support":
            await event.answer("🛠️ 技术支持联系方式: @SupportBot", alert=True)

        # 3. Utility
        elif action in ["exit", "close"]:
            await event.delete()
        
        elif action == "forward_search":
            await new_menu_system.show_forward_search(event)

        # 4. System Settings & Maintenance
        elif action == "system_settings":
            await new_menu_system.show_system_settings(event)

        elif action == "system_overview":
            await new_menu_system.show_system_overview(event)

        elif action == "cache_cleanup":
            await menu_controller.show_cache_cleanup(event)
        
        elif action == "do_cleanup":
            await new_menu_system.do_cache_cleanup(event)
        
        elif action == "refresh_main_menu":
            await menu_controller.show_main_menu(event, force_refresh=True)
            await event.answer("✅ 主菜单已刷新")
        
        elif action == "log_viewer":
            await menu_controller.show_system_logs(event)
        
        elif action == "system_logs":
            await menu_controller.show_system_logs(event)
        
        elif action == "system_status":
            await new_menu_system.show_system_status(event)
        
        elif action == "db_archive_once":
            await menu_controller.run_db_archive_once(event)

        elif action == "db_archive_center":
            # 内部暂无专用 Archive Hub，先引导至优化中心或执行一次性归档
            await menu_controller.show_db_optimization_center(event)
        
        elif action == "session_management":
            await menu_controller.show_session_management(event)

        # 6. Database Optimization & Performance
        elif action == "db_optimization_center":
            await menu_controller.show_db_optimization_center(event)
        
        elif action == "db_performance_monitor":
            await menu_controller.show_db_performance_monitor(event)
        
        elif action == "refresh_db_performance":
            await menu_controller.refresh_db_performance(event)
        
        elif action == "db_query_analysis":
            await menu_controller.show_db_query_analysis(event)
        
        elif action == "db_performance_trends":
            await menu_controller.show_db_performance_trends(event)
        
        elif action == "db_alert_management":
            await menu_controller.show_db_alert_management(event)
        
        elif action == "run_db_optimization_check":
            await menu_controller.run_db_optimization_check(event)
        
        elif action == "db_reindex":
            await menu_controller.run_db_reindex(event)
        
        elif action == "db_optimization_config":
            await menu_controller.show_db_optimization_config(event)
        
        elif action == "clear_dedup_cache":
            await menu_controller.clear_dedup_cache(event)

        # 5. Backup & Restore
        elif action == "db_backup":
            await menu_controller.show_db_backup(event)
        
        elif action == "backup_current":
            await new_menu_system.confirm_backup(event)
        
        elif action == "do_backup":
            await new_menu_system.do_backup(event)
        
        elif action == "view_backups":
            await new_menu_system.show_backup_history(event)
        
        elif action == "backup_page":
            page = int(extra_data[0]) if extra_data else 0
            await new_menu_system.show_backup_history(event, page)
        
        elif action == "restore_backup":
            backup_id = int(extra_data[0]) if extra_data else 0
            await new_menu_system.confirm_restore_backup(event, backup_id)
        
        elif action == "do_restore":
            backup_id = int(extra_data[0]) if extra_data else 0
            await new_menu_system.do_restore(event, backup_id)
