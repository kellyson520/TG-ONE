import logging
from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from core.container import container
from telethon import Button

logger = logging.getLogger(__name__)

@MenuHandlerRegistry.register
class UFBMenuStrategy(BaseMenuHandler):
    """
    Handles UFB (Ultra Fast Binding?) and Other Settings actions.
    """
    ACTIONS = {
        "ufb_item", "other_settings"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        extra_data = kwargs.get("extra_data", [])
        
        rule_id = int(extra_data[0]) if extra_data and extra_data[0].isdigit() else 0

        if action == "ufb_item":
            item_type = extra_data[1] if len(extra_data) > 1 else "main"
            await menu_controller.handle_ufb_item(event, item_type)
        elif action == "other_settings":
            await menu_controller.show_other_settings(event, rule_id)
        else:
            await event.answer("⚠️ 未知操作", alert=True)
