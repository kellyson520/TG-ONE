import logging
import traceback
from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from core.container import container

logger = logging.getLogger(__name__)

@MenuHandlerRegistry.register
class MediaMenuStrategy(BaseMenuHandler):
    """
    Handles Media-related settings actions for a specific rule.
    """
    ACTIONS = {
        "media_settings",
        "set_max_media_size", "select_max_media_size",
        "set_media_types", "toggle_media_type",
        "set_media_extensions", "media_extensions_page", "toggle_media_extension",
        "toggle_media_allow_text"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        extra_data = kwargs.get("extra_data", [])
        
        # rule_id extraction
        rule_id = None
        if extra_data and extra_data[0].isdigit():
            rule_id = int(extra_data[0])
        elif ":" in kwargs.get("data", ""):
            parts = kwargs.get("data").split(":")
            if len(parts) > 1 and parts[1].isdigit():
                rule_id = int(parts[1])

        if not rule_id:
            logger.warning(f"MediaStrategy: No rule_id for action {action}")
            return await event.answer("⚠️ 参数错误", alert=True)

        if action == "media_settings":
            await menu_controller.show_media_settings(event, rule_id)
        elif action == "set_max_media_size":
            await menu_controller.show_max_media_size_selection(event, rule_id)
        elif action == "select_max_media_size":
            size = int(extra_data[1]) if len(extra_data) > 1 else 0
            await menu_controller.set_max_media_size(event, rule_id, size)
        elif action == "set_media_types":
            await menu_controller.show_media_types_selection(event, rule_id)
        elif action == "toggle_media_type":
            media_type = extra_data[1] if len(extra_data) > 1 else None
            if media_type: await menu_controller.toggle_media_type(event, rule_id, media_type)
        elif action == "set_media_extensions":
            await menu_controller.show_media_extensions_page(event, rule_id, page=0)
        elif action == "media_extensions_page":
            page = int(extra_data[1]) if len(extra_data) > 1 else 0
            await menu_controller.show_media_extensions_page(event, rule_id, page)
        elif action == "toggle_media_extension":
            extension = extra_data[1] if len(extra_data) > 1 else None
            page = int(extra_data[2]) if len(extra_data) > 2 else 0
            if extension: await menu_controller.toggle_media_extension(event, rule_id, extension, page)
        elif action == "toggle_media_allow_text":
            await menu_controller.toggle_media_boolean(event, rule_id, "media_allow_text")
        else:
            logger.warning(f"MediaStrategy: Action {action} not mapped")
            await event.answer("⚠️ 功能开发中", alert=True)
