from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from core.container import container
from telethon import Button

@MenuHandlerRegistry.register
class RuleMenuStrategy(BaseMenuHandler):
    """
    Handles Rule Management actions:
    - List Rules
    - Rule Details
    - Add/Edit/Delete Rules
    - Keyword/Replace Management
    - Rule Settings (Basic, Display, Advanced)
    - Multi-source Management
    - Sync Config
    """

    ACTIONS = {
        "list_rules", "rule_detail", "toggle_rule",
        "delete_rule_confirm", "delete_rule_do",
        "keywords", "add_keyword", "clear_keywords_confirm", "clear_keywords_do",
        "replaces", "add_replace", "clear_replaces_confirm", "clear_replaces_do",
        "rule_basic_settings", "rule_display_settings", "rule_advanced_settings",
        "toggle_rule_set",
        "rule_status", "sync_config",
        "forward_management", "rule_management",
        "multi_source_management", "multi_source_page", "manage_multi_source",
        "history_messages", "forward_stats_detailed", "global_forward_settings",
        "forward_performance"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        from handlers.button.new_menu_system import new_menu_system

        extra_data = kwargs.get("extra_data", [])
        
        # Helper to get first int arg safely
        arg1 = int(extra_data[0]) if extra_data and extra_data[0] else 0

        # 1. Rule Listing & Navigation
        if action == "list_rules":
            page = arg1
            await menu_controller.show_rule_list(event, page=page)
        
        elif action in ["forward_management", "rule_management"]:
            await new_menu_system.show_rule_management(event)

        elif action == "rule_detail":
            rule_id = arg1
            await menu_controller.show_rule_detail(event, rule_id)
        
        elif action == "rule_status":
             rule_id = arg1
             await menu_controller.show_rule_status(event, rule_id)

        # 2. Rule Actions
        elif action == "toggle_rule":
            rule_id = arg1
            await menu_controller.toggle_rule_status(event, rule_id)
        
        elif action == "delete_rule_confirm":
            rule_id = arg1
            await menu_controller.delete_rule_confirm(event, rule_id)
        
        elif action == "delete_rule_do":
            rule_id = arg1
            await menu_controller.delete_rule_do(event, rule_id)

        # 3. Keywords & Replaces
        elif action == "keywords":
            rule_id = arg1
            await menu_controller.show_manage_keywords(event, rule_id)
        
        elif action == "add_keyword":
            rule_id = arg1
            await menu_controller.enter_add_keyword_state(event, rule_id)
        
        elif action == "clear_keywords_confirm":
            rule_id = arg1
            await menu_controller.clear_keywords_confirm(event, rule_id)
        
        elif action == "clear_keywords_do":
            rule_id = arg1
            await menu_controller.clear_keywords_do(event, rule_id)
        
        elif action == "replaces":
            rule_id = arg1
            await menu_controller.show_manage_replace_rules(event, rule_id)
        
        elif action == "add_replace":
            rule_id = arg1
            await menu_controller.enter_add_replace_state(event, rule_id)
        
        elif action == "clear_replaces_confirm":
            rule_id = arg1
            await menu_controller.clear_replaces_confirm(event, rule_id)
        
        elif action == "clear_replaces_do":
            rule_id = arg1
            await menu_controller.clear_replaces_do(event, rule_id)

        # 4. Settings Taps
        elif action == "rule_basic_settings":
            rule_id = arg1
            await menu_controller.show_rule_basic_settings(event, rule_id)
        
        elif action == "rule_display_settings":
            rule_id = arg1
            await menu_controller.show_rule_display_settings(event, rule_id)
        
        elif action == "rule_advanced_settings":
            rule_id = arg1
            await menu_controller.show_rule_advanced_settings(event, rule_id)
        
        elif action == "toggle_rule_set":
            rule_id = arg1
            key = extra_data[1] if len(extra_data) > 1 else ""
            await menu_controller.toggle_rule_setting_new(event, rule_id, key)

        elif action == "sync_config":
            rule_id = arg1
            await menu_controller.show_sync_config(event, rule_id)

        # 5. Multi-Source
        elif action in ["multi_source_management", "multi_source_page"]:
            page = arg1
            await menu_controller.show_multi_source_management(event, page)
        
        elif action == "manage_multi_source":
            rule_id = arg1
            await menu_controller.show_multi_source_detail(event, rule_id)
        
        # 6. History Messages \u0026 Extended Features
        elif action == "history_messages":
            await menu_controller.show_history_messages(event)
        
        elif action == "forward_stats_detailed":
            await event.answer("📊 详细统计功能开发中", alert=True)
        
        elif action == "global_forward_settings":
            await event.answer("🎛️ 全局筛选功能开发中", alert=True)
        
        elif action == "forward_performance":
            await event.answer("🚀 性能监控功能开发中", alert=True)
