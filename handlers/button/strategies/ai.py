import logging
import traceback
from telethon import events
from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from core.container import container

logger = logging.getLogger(__name__)

@MenuHandlerRegistry.register
class AIMenuStrategy(BaseMenuHandler):
    """
    Handles AI-related settings actions.
    """
    ACTIONS = {
        "ai_settings", "ai_global_settings",
        "ai_global_model", "ai_global_concurrency",
        "select_global_ai_model", "set_global_ai_concurrency",
        "set_summary_time", "set_summary_prompt", "set_ai_prompt",
        "time_page", "select_time",
        "select_model", "model_page", "change_model",
        "cancel_set_prompt", "cancel_set_summary",
        "summary_now"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event: events.CallbackQuery.Event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        extra_data = kwargs.get("extra_data", [])
        data = kwargs.get("data")
        
        # rule_id extraction
        rule_id = int(extra_data[0]) if extra_data and extra_data[0].isdigit() else 0
        if not rule_id and ":" in data:
            parts = data.split(":")
            if len(parts) > 1 and parts[1].isdigit():
                rule_id = int(parts[1])

        from handlers.button.new_menu_system import new_menu_system
        if action == "ai_global_settings":
            return await new_menu_system.show_ai_global_settings(event)

        elif action == "ai_global_model":
            return await new_menu_system.show_ai_global_model(event)

        elif action == "ai_global_concurrency":
            return await new_menu_system.show_ai_global_concurrency(event)

        elif action == "select_global_ai_model":
            model = extra_data[0] if extra_data else ""
            return await new_menu_system.select_global_ai_model(event, model)

        elif action == "set_global_ai_concurrency":
            val = int(extra_data[0]) if extra_data else 5
            return await new_menu_system.set_global_ai_concurrency(event, val)

        if action == "ai_settings":
            await menu_controller.show_ai_settings(event, rule_id)
        
        elif action == "set_summary_time":
            await menu_controller.show_summary_time_selection(event, rule_id)
        
        elif action == "set_summary_prompt":
            await menu_controller.enter_set_ai_prompt_state(event, rule_id, is_summary=True)
        
        elif action == "set_ai_prompt":
            await menu_controller.enter_set_ai_prompt_state(event, rule_id, is_summary=False)
        
        elif action == "time_page":
            page = int(extra_data[1]) if len(extra_data) > 1 else 0
            await menu_controller.show_summary_time_selection(event, rule_id, page=page)
        
        elif action == "select_time":
            time_val = extra_data[1] if len(extra_data) > 1 else ""
            await menu_controller.select_summary_time(event, rule_id, time_val)
        
        elif action == "select_model":
            model_name = extra_data[1] if len(extra_data) > 1 else ""
            await menu_controller.select_ai_model(event, rule_id, model_name)

        elif action == "model_page":
            page = int(extra_data[1]) if len(extra_data) > 1 else 0
            await menu_controller.show_model_selection(event, rule_id, page=page)
            
        elif action == "change_model":
            await menu_controller.show_model_selection(event, rule_id)

        elif action in ["cancel_set_prompt", "cancel_set_summary"]:
            await menu_controller.cancel_ai_state(event, rule_id)
        
        elif action == "summary_now":
            await menu_controller.run_summary_now(event, rule_id)
        
        else:
            logger.warning(f"AIStrategy: No handler for action {action}")
