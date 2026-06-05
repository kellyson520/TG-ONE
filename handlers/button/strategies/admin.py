import logging
from telethon import events
from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from core.container import container

logger = logging.getLogger(__name__)

@MenuHandlerRegistry.register
class AdminMenuStrategy(BaseMenuHandler):
    """
    Handles Admin Panel actions.
    """
    ACTIONS = {
        "admin_db_info", "admin_db_health",
        "admin_db_backup", "admin_db_optimize",
        "admin_system_status", "admin_logs",
        "admin_cleanup_menu", "admin_cleanup", "admin_cleanup_temp",
        "admin_vacuum_db", "admin_analyze_db", "admin_full_optimize",
        "admin_stats", "admin_config",
        "admin_restart", "admin_restart_confirm",
        "admin_panel", "close_admin_panel", "close"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event: events.CallbackQuery.Event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        extra_data = kwargs.get("extra_data", [])
        
        # Dispatch admin actions to controller
        if action == "admin_panel":
            await menu_controller.show_admin_panel(event)
        
        elif action == "admin_db_info":
            await menu_controller.run_admin_db_cmd(event, "info")
        elif action == "admin_db_health":
            await menu_controller.run_admin_db_cmd(event, "health")
        elif action == "admin_db_backup":
            await menu_controller.run_admin_db_cmd(event, "backup")
        elif action == "admin_db_optimize":
            await menu_controller.run_admin_db_cmd(event, "optimize")
        elif action == "admin_system_status":
            await menu_controller.run_admin_db_cmd(event, "status")
        
        elif action == "admin_logs":
            await menu_controller.show_admin_logs(event)
        
        elif action == "admin_cleanup_menu":
            await menu_controller.show_admin_cleanup_menu(event)
        
        elif action == "admin_cleanup":
            days = int(extra_data[0]) if extra_data else 7
            await menu_controller.execute_admin_cleanup_logs(event, days)
        
        elif action == "admin_cleanup_temp":
            await menu_controller.execute_cleanup_temp(event)
            
        elif action == "admin_vacuum_db":
            await menu_controller.run_db_reindex(event)
            
        elif action == "admin_analyze_db":
            await menu_controller.show_db_detailed_report(event)
            
        elif action == "admin_full_optimize":
            await menu_controller.run_db_optimization_check(event)
            
        elif action == "admin_stats":
            await menu_controller.show_admin_stats(event)
        
        elif action == "admin_config":
            await menu_controller.show_config(event)
            
        elif action == "admin_restart":
            await menu_controller.show_restart_confirm(event)
            
        elif action == "admin_restart_confirm":
            await menu_controller.execute_restart(event)
        
        elif action in ["close_admin_panel", "close"]:
            await event.delete()
        
        else:
            logger.warning(f"AdminStrategy: No handler for action {action}")
