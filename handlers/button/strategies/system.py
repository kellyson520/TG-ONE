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
        "clear_dedup_cache", "run_archive_once", "run_archive_force",
        "rebuild_bloom", "compact_archive",
        "db_index_analysis", "db_cache_management",
        "detailed_analytics", "performance_analysis", "anomaly_detection",
        "export_csv", "export_csv_report", "failure_analysis", "export_error_logs"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        from handlers.button.new_menu_system import new_menu_system

        extra_data = kwargs.get("extra_data", [])

        if action in ("main_menu", "main"):
            await menu_controller.show_main_menu(event)
        elif action == "main_menu_refresh":
            await menu_controller.show_main_menu(event, force_refresh=True)
            await event.answer("✅ 数据看板已刷新")
        elif action in ("exit", "close"):
            await event.delete()
        elif action == "forward_search":
            await new_menu_system.show_forward_search(event)
        elif action == "tech_support":
            await event.answer("🛠️ 技术支持联系方式: @SupportBot", alert=True)
        elif action == "refresh_main_menu":
            await menu_controller.show_main_menu(event, force_refresh=True)
            await event.answer("✅ 主菜单已刷新")
        else:
            await self._handle_hub_and_analytics(event, action, extra_data, menu_controller, new_menu_system)

    async def _handle_hub_and_analytics(self, event, action, extra_data, mc, nms):
        if action == "forward_hub":
            await mc.show_forward_hub(event)
        elif action == "refresh_forward_hub":
            await mc.show_forward_hub(event, force_refresh=True)
            await event.answer("✅ 转发中心已刷新")
        elif action == "dedup_hub":
            await mc.show_dedup_hub(event)
        elif action == "analytics_hub":
            await mc.show_analytics_hub(event)
        elif action == "system_hub":
            await mc.show_system_hub(event)
        elif action == "detailed_analytics":
            await mc.show_detailed_analytics(event)
        elif action == "performance_analysis":
            await mc.show_performance_analysis(event)
        elif action == "anomaly_detection":
            await mc.show_anomaly_detection(event)
        elif action in ("export_csv", "export_csv_report"):
            await mc.export_csv_report(event)
        elif action == "export_error_logs":
            await mc.export_error_logs(event)
        elif action == "failure_analysis":
            await mc.show_failure_analysis(event)
        elif action == "help_guide":
            await mc.show_help_guide(event)
        elif action == "detailed_docs":
            await mc.show_detailed_docs(event)
        elif action == "faq":
            await mc.show_faq(event)
        else:
            await self._handle_system_maintenance(event, action, extra_data, mc, nms)

    async def _handle_system_maintenance(self, event, action, extra_data, mc, nms):
        if action == "system_settings":
            await nms.show_system_settings(event)
        elif action == "system_overview":
            await nms.show_system_overview(event)
        elif action == "cache_cleanup":
            await mc.show_cache_cleanup(event)
        elif action == "do_cleanup":
            await nms.do_cache_cleanup(event)
        elif action in ("log_viewer", "system_logs"):
            await mc.show_system_logs(event)
        elif action == "system_status":
            await nms.show_system_status(event)
        elif action == "db_archive_once":
            await mc.run_db_archive_once(event)
        elif action == "db_archive_center":
            await mc.show_db_archive_center(event)
        elif action == "session_management":
            await mc.show_session_management(event)
        elif action == "db_optimization_center":
            await mc.show_db_optimization_center(event)
        elif action == "db_performance_monitor":
            await mc.show_db_performance_monitor(event)
        elif action == "refresh_db_performance":
            await mc.refresh_db_performance(event)
        elif action == "db_query_analysis":
            await mc.show_db_query_analysis(event)
        elif action == "db_performance_trends":
            await mc.show_db_performance_trends(event)
        elif action == "db_alert_management":
            await mc.show_db_alert_management(event)
        elif action == "run_db_optimization_check":
            await mc.run_db_optimization_check(event)
        elif action == "db_reindex":
            await mc.run_db_reindex(event)
        elif action == "db_optimization_config":
            await mc.show_db_optimization_config(event)
        elif action == "clear_dedup_cache":
            await mc.clear_dedup_cache(event)
        elif action == "run_archive_once":
            await nms.run_archive_once(event)
        elif action == "run_archive_force":
            await nms.run_archive_force(event)
        elif action == "rebuild_bloom":
            await nms.rebuild_bloom(event)
        elif action == "compact_archive":
            await nms.compact_archive(event)
        elif action == "db_index_analysis":
            await mc.show_db_index_analysis(event)
        elif action == "db_cache_management":
            await mc.show_db_cache_management(event)
        else:
            await self._handle_backup_restore(event, action, extra_data, mc, nms)

    async def _handle_backup_restore(self, event, action, extra_data, mc, nms):
        if action == "db_backup":
            await mc.show_db_backup(event)
        elif action == "backup_current":
            await nms.confirm_backup(event)
        elif action == "do_backup":
            await nms.do_backup(event)
        elif action == "view_backups":
            await nms.show_backup_history(event)
        elif action == "backup_page":
            page = int(extra_data[0]) if extra_data else 0
            await nms.show_backup_history(event, page)
        elif action == "restore_backup":
            backup_id = int(extra_data[0]) if extra_data else 0
            await nms.confirm_restore_backup(event, backup_id)
        elif action == "do_restore":
            backup_id = int(extra_data[0]) if extra_data else 0
            await nms.do_restore(event, backup_id)
