import logging
from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry

logger = logging.getLogger(__name__)

@MenuHandlerRegistry.register
class CopyMenuStrategy(BaseMenuHandler):
    """
    Handles Rule Copy actions.
    Now a pure handler delegating to MenuController.
    """
    ACTIONS = {"copy_rule_settings", "copy_rules_page", "perform_copy_rule"}

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        extra_data = kwargs.get("extra_data", [])
        
        # rule_id extraction
        rule_id = int(extra_data[0]) if extra_data and extra_data[0].isdigit() else 0

        if action == "copy_rule_settings":
            await menu_controller.show_copy_rule_selection(event, rule_id)
            
        elif action == "copy_rules_page":
            page = int(extra_data[1]) if len(extra_data) > 1 else 0
            await menu_controller.show_copy_rule_selection(event, rule_id, page=page)
            
        elif action == "perform_copy_rule":
            target_id = int(extra_data[1]) if len(extra_data) > 1 else 0
            if rule_id and target_id:
                await menu_controller.perform_rule_copy(event, rule_id, target_id)
            else:
                await event.answer("⚠️ 参数错误", alert=True)
                
        else:
            logger.warning(f"CopyStrategy: No handler for action {action}")
