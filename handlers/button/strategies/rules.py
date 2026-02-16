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
        "list_rules", "rule_list_page", "rule_detail", "edit_rule", "toggle_rule",
        "delete_rule_confirm", "delete_rule_do",
        "keywords", "add_keyword", "kw_add", "clear_keywords_confirm", "clear_keywords_do",
        "replaces", "add_replace", "rr_add", "clear_replaces_confirm", "clear_replaces_do",
        "rule_basic_settings", "rule_display_settings", "rule_advanced_settings",
        "toggle_rule_set", "set_rule_val", "media_settings", "ai_settings",
        "rule_status", "sync_config", "rule_sync_push", "sync_rule_page", "toggle_rule_sync",
        "create_rule", "rule_statistics", "search_rules",
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
        if action in ["list_rules", "rule_list_page"]:
            page = arg1
            await menu_controller.show_rule_list(event, page=page)
        
        elif action in ["forward_management", "rule_management"]:
            await new_menu_system.show_rule_management(event)

        elif action in ["rule_detail", "edit_rule"]:
            rule_id = arg1
            await menu_controller.show_rule_detail(event, rule_id)
        
        elif action == "create_rule":
            await event.answer("➕ 请使用 /bind 或网页端创建规则", alert=True)

        elif action == "rule_statistics":
            await menu_controller.show_rule_statistics(event)

        elif action == "search_rules":
            await event.answer("🔍 搜索规则功能已集成在列表页", alert=True)

        elif action == "rule_status":
             rule_id = arg1
             await menu_controller.show_rule_status(event, rule_id)

        # 2. Rule Actions
        elif action == "toggle_rule":
            rule_id = arg1
            from_page = extra_data[1] if len(extra_data) > 1 else "detail"
            page = int(extra_data[2]) if len(extra_data) > 2 else 0
            await menu_controller.toggle_rule_status(event, rule_id, from_page, page)
        
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
        
        elif action in ["add_keyword", "kw_add"]:
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
        
        elif action in ["add_replace", "rr_add"]:
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
        
        elif action == "media_settings":
            rule_id = arg1
            await menu_controller.show_media_settings(event, rule_id)

        elif action == "ai_settings":
            rule_id = arg1
            await menu_controller.show_ai_settings(event, rule_id)

        elif action == "toggle_rule_set":
            rule_id = arg1
            key = extra_data[1] if len(extra_data) > 1 else ""
            await menu_controller.toggle_setting(event, rule_id, key)

        elif action == "set_rule_val":
            rule_id = arg1
            key = extra_data[1] if len(extra_data) > 1 else ""
            await menu_controller.enter_set_value_state(event, rule_id, key)

        elif action in ["sync_config", "rule_sync_push"]:
            rule_id = arg1
            await menu_controller.show_sync_config(event, rule_id)

        elif action == "sync_rule_page":
            rule_id = arg1
            page = int(extra_data[1]) if len(extra_data) > 1 else 0
            await menu_controller.show_sync_rule_picker(event, rule_id, page)

        elif action == "toggle_rule_sync":
            rule_id = arg1
            target_id = int(extra_data[1]) if len(extra_data) > 1 else 0
            page = int(extra_data[2]) if len(extra_data) > 2 else 0
            await menu_controller.toggle_rule_sync(event, rule_id, target_id, page)

        # 5. Multi-Source
        elif action in ["multi_source_management", "multi_source_page"]:
            page = arg1
            await menu_controller.show_multi_source_management(event, page)
        
        elif action == "manage_multi_source":
            rule_id = arg1
            await menu_controller.show_multi_source_detail(event, rule_id)
        
        # 6. History Messages & Extended Features
        elif action == "history_messages":
            await menu_controller.show_history_messages(event)
        
        elif action == "forward_stats_detailed":
            await new_menu_system.show_detailed_analytics(event)
        
        elif action == "global_forward_settings":
            await new_menu_system.show_filter_settings(event)
        
        elif action == "forward_performance":
            await new_menu_system.show_performance_analysis(event)
