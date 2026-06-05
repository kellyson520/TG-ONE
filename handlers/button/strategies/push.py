import logging
import traceback
from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from core.container import container
from handlers.button.callback.push_callback import (
    callback_push_settings,
    callback_toggle_enable_push,
    callback_toggle_enable_only_push,
    callback_add_push_channel,
    callback_cancel_add_push_channel,
    callback_toggle_push_config,
    callback_toggle_push_config_status,
    callback_toggle_media_send_mode,
    callback_delete_push_config,
    callback_push_page,
)

logger = logging.getLogger(__name__)

@MenuHandlerRegistry.register
class PushMenuStrategy(BaseMenuHandler):
    """
    Handles Push Notification settings actions.
    """
    ACTIONS = {
        "push_settings",
        "toggle_enable_push", "toggle_enable_only_push",
        "add_push_channel", "cancel_add_push_channel",
        "toggle_push_config", "toggle_push_config_status",
        "toggle_media_send_mode", "delete_push_config",
        "push_page"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        extra_data = kwargs.get("extra_data", [])
        data = kwargs.get("data", "")
        
        # ID extraction (rule_id or config_id)
        id_param = None
        if extra_data and extra_data[0].isdigit():
            id_param = int(extra_data[0])
        elif ":" in data:
            parts = data.split(":")
            if len(parts) > 1 and parts[1].isdigit():
                id_param = int(parts[1])

        if not id_param:
            logger.warning(f"PushStrategy: No ID for action {action}")
            return await event.answer("⚠️ 参数错误", alert=True)

        if action == "push_settings":
            await menu_controller.show_push_settings(event, id_param)
        elif action == "toggle_enable_push":
            await menu_controller.toggle_push_boolean(event, id_param, "enable_push")
        elif action == "toggle_enable_only_push":
            await menu_controller.toggle_push_boolean(event, id_param, "enable_only_push")
        elif action == "add_push_channel":
            await menu_controller.enter_add_push_channel_state(event, id_param)
        elif action == "cancel_add_push_channel":
            # Just show settings again
            await menu_controller.show_push_settings(event, id_param)
        elif action == "toggle_push_config":
            await menu_controller.show_push_config_details(event, id_param)
        elif action == "toggle_push_config_status":
            await menu_controller.toggle_push_config_status(event, id_param)
        elif action == "toggle_media_send_mode":
            await menu_controller.toggle_media_send_mode(event, id_param)
        elif action == "delete_push_config":
            await menu_controller.delete_push_config(event, id_param)
        elif action == "push_page":
            page = int(extra_data[1]) if len(extra_data) > 1 else 0
            await menu_controller.show_push_settings(event, id_param, page)
        else:
            logger.warning(f"PushStrategy: Action {action} not mapped")
            await event.answer("⚠️ 功能开发中", alert=True)
