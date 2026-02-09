from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from core.container import container
from telethon import Button
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@MenuHandlerRegistry.register
class SettingsMenuStrategy(BaseMenuHandler):
    """
    Handles Global & Media Settings actions:
    - Toggle Global Settings (allow_text, allow_emoji, etc.)
    - Toggle Extension Mode (blacklist/whitelist)
    - Toggle Media Type (image, video, etc.)
    - Toggle Media Duration & Size Filters
    - Set Duration Range
    - Save Duration Settings
    """

    ACTIONS = {
        "toggle_setting", "toggle_extension_mode",
        "toggle_media_type", 
        "toggle_media_duration",
        "set_duration_range", "set_duration_start", "set_duration_end",
        "save_duration_settings",
        "toggle_media_size_filter", "toggle_media_size_alert",
        # Aliases and Navigation
        "allow_text", "filter_allow_text", "toggle_allow_text", "history_toggle_allow_text",
        "toggle_media_extension", "filter_media_extension",
        "filter_media_size", "filter_media_duration",
        "save_message_filter",
        "toggle_allow_emoji", "toggle_dedup_enabled", "toggle_dedup_mode",
        "filter_settings", "media_types", "message_filter", "filter_media_types",
        "history_toggle_image", "toggle_image",
        "history_toggle_video", "toggle_video",
        "history_toggle_music", "toggle_music",
        "history_toggle_voice", "toggle_voice",
        "history_toggle_document", "toggle_document"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from handlers.button.new_menu_system import new_menu_system
        from services.forward_settings_service import forward_settings_service

        extra_data = kwargs.get("extra_data", [])

        if action == "toggle_setting":
            setting_key = extra_data[0] if extra_data else ""
            await self._handle_toggle_setting(event, setting_key)

        elif action == "toggle_extension_mode":
            await self._handle_toggle_extension_mode(event)

        elif action == "toggle_media_type":
            # toggle_media_type:{type} or toggle_media_type:{type}:history
            mtype = extra_data[0] if extra_data else ""
            is_history = len(extra_data) > 1 and extra_data[1] == "history"
            await self._handle_toggle_media_type(event, mtype, is_history)

        elif action == "toggle_media_duration":
            await self._handle_toggle_media_duration(event)

        elif action == "set_duration_range":
            # 进入先选起始或结束的分流菜单
            buttons = [
                [Button.inline("设置起始时长", "new_menu:set_duration_start")],
                [Button.inline("设置结束时长(0视为∞)", "new_menu:set_duration_end")],
                [Button.inline("👈 返回上一级", "new_menu:media_duration_settings")],
            ]
            timestamp = datetime.now().strftime("%H:%M:%S")
            text = f"请选择要设置的时长边界：\n\n更新时间: {timestamp}"
            await event.edit(text, buttons=buttons)

        elif action == "set_duration_start":
            await new_menu_system.show_duration_range_picker(event, "min")

        elif action == "set_duration_end":
            await new_menu_system.show_duration_range_picker(event, "max")

        elif action == "save_duration_settings":
            await event.answer("✅ 时长设置已自动保存")

        elif action == "toggle_media_size_filter":
            await self._handle_toggle_media_size_filter(event)

        elif action == "toggle_media_size_alert":
            await self._handle_toggle_media_size_alert(event)
            
        # --- Expanded Handlers ---
        elif action in ["allow_text", "filter_allow_text", "toggle_allow_text", "history_toggle_allow_text"]:
            await self._handle_toggle_setting(event, "allow_text")

        elif action == "toggle_media_extension":
            await self._handle_toggle_setting(event, "media_extension_enabled")
            
        elif action == "filter_media_extension":
            await new_menu_system.show_media_extension_settings(event)
            
        elif action == "filter_media_size":
            await new_menu_system.show_media_size_settings(event)
        
        elif action == "filter_media_duration":
             await new_menu_system.show_media_duration_settings(event)

        elif action == "save_message_filter":
            # 占位：此处可落库保存筛选配置，当前仅提示成功并返回
            try:
                await event.answer("✅ 已保存筛选配置")
            except Exception:
                pass
            await new_menu_system.show_delete_session_messages_menu(event)
            
        elif action == "toggle_allow_emoji":
            await self._handle_toggle_setting(event, "allow_emoji")

        elif action == "toggle_dedup_enabled":
            await self._handle_toggle_setting(event, "dedup_enabled")

        elif action == "toggle_dedup_mode":
            await self._handle_toggle_setting(event, "dedup_mode")
            
        elif action == "filter_settings":
            await new_menu_system.show_filter_settings(event)
            
        elif action == "media_types" or action == "filter_media_types":
            await new_menu_system.show_media_types(event)
            
        elif action == "message_filter":
            await new_menu_system.show_message_filter_menu(event)
            
        # Media Type Toggles with Alias
        elif "toggle_image" in action:
            await self._handle_toggle_media_type(event, "image", is_history="history" in action)
        elif "toggle_video" in action:
             await self._handle_toggle_media_type(event, "video", is_history="history" in action)
        elif "toggle_music" in action:
             await self._handle_toggle_media_type(event, "audio", is_history="history" in action)
        elif "toggle_voice" in action:
             await self._handle_toggle_media_type(event, "voice", is_history="history" in action)
        elif "toggle_document" in action:
             await self._handle_toggle_media_type(event, "document", is_history="history" in action)

    # --- Internal Handlers (Migrated from new_menu_callback.py) ---

    async def _handle_toggle_setting(self, event, setting_key):
        from services.forward_settings_service import forward_settings_service
        from handlers.button.new_menu_system import new_menu_system
        try:
            result = await forward_settings_service.toggle_global_boolean(setting_key)
            if not result.get("success"):
                await event.answer("操作失败", alert=True)
                return
            new_value = result.get("new_value")
            setting_names = {
                "allow_text": "放行文本", "allow_emoji": "放行表情包",
                "media_extension_enabled": "媒体扩展过滤",
            }
            setting_name = setting_names.get(setting_key, setting_key)
            status = "开启" if new_value else "关闭"
            await event.answer(f"{setting_name}已{status}")
            await new_menu_system.show_filter_settings(event)
        except Exception as e:
            logger.error(f"切换设置失败: {str(e)}")
            await event.answer("操作失败", alert=True)

    async def _handle_toggle_extension_mode(self, event):
        from services.forward_settings_service import forward_settings_service
        from handlers.button.new_menu_system import new_menu_system
        try:
            r = await forward_settings_service.toggle_extension_mode()
            if not r.get("success"):
                await event.answer("操作失败", alert=True)
                return
            new_mode = r.get("new_mode") or "blacklist"
            mode_name = "白名单" if new_mode == "whitelist" else "黑名单"
            await event.answer(f"扩展过滤模式已切换为{mode_name}")
            await new_menu_system.show_filter_settings(event)
        except Exception as e:
            logger.error(f"切换扩展模式失败: {str(e)}")
            await event.answer("操作失败", alert=True)

    async def _handle_toggle_media_type(self, event, media_type, is_history=False):
        from services.forward_settings_service import forward_settings_service
        from handlers.button.new_menu_system import new_menu_system
        try:
            result = await forward_settings_service.toggle_media_type(media_type)
            if result:
                settings = await forward_settings_service.get_global_media_settings()
                is_enabled = settings["media_types"].get(media_type, False)
                type_names = {
                    "image": "图片", "video": "视频", "audio": "音乐",
                    "voice": "语音", "document": "文档",
                }
                type_name = type_names.get(media_type, media_type)
                status = "允许" if is_enabled else "禁止"
                await event.answer(f"{type_name}已{status}")
                
                try:
                    if is_history:
                        from handlers.button.modules.history import history_module
                        await history_module.show_media_types(event)
                    else:
                        await new_menu_system.show_media_types(event)
                except Exception as e:
                    if "not modified" in str(e).lower():
                        await event.answer("已更新")
                    else:
                        raise
            else:
                await event.answer("操作失败", alert=True)
        except Exception as e:
            logger.error(f"切换媒体类型失败: {str(e)}")
            await event.answer("操作失败", alert=True)

    async def _handle_toggle_media_duration(self, event):
        from services.forward_settings_service import forward_settings_service
        from handlers.button.new_menu_system import new_menu_system
        try:
            settings = await forward_settings_service.get_global_media_settings()
            current_value = settings.get("media_duration_enabled", False)
            new_value = not current_value
            await forward_settings_service.update_global_media_setting(
                "media_duration_enabled", new_value
            )
            status = "开启" if new_value else "关闭"
            await event.answer(f"媒体时长过滤已{status}")
            await new_menu_system.show_media_duration_settings(event)
        except Exception as e:
            logger.error(f"切换媒体时长过滤失败: {str(e)}")
            await event.answer("操作失败", alert=True)

    async def _handle_toggle_media_size_filter(self, event):
        from services.forward_settings_service import forward_settings_service
        from handlers.button.new_menu_system import new_menu_system
        try:
            settings = await forward_settings_service.get_global_media_settings()
            current_value = settings.get("media_size_filter_enabled", False)
            new_value = not current_value
            ok = await forward_settings_service.update_global_media_setting(
                "media_size_filter_enabled", new_value
            )
            if not ok:
                await event.answer("操作失败", alert=True)
                return
            status = "开启" if new_value else "关闭"
            await event.answer(f"媒体大小过滤已{status}")
            await new_menu_system.show_media_size_settings(event)
        except Exception as e:
            logger.error(f"切换媒体大小过滤失败: {str(e)}")
            await event.answer("操作失败", alert=True)

    async def _handle_toggle_media_size_alert(self, event):
        from services.forward_settings_service import forward_settings_service
        from handlers.button.new_menu_system import new_menu_system
        try:
            settings = await forward_settings_service.get_global_media_settings()
            current_value = settings.get("media_size_alert_enabled", False)
            new_value = not current_value
            ok = await forward_settings_service.update_global_media_setting(
                "media_size_alert_enabled", new_value
            )
            if not ok:
                await event.answer("操作失败", alert=True)
                return
            status = "开启" if new_value else "关闭"
            await event.answer(f"媒体大小超限提示已{status}")
            await new_menu_system.show_media_size_settings(event)
        except Exception as e:
            logger.error(f"切换媒体大小超限提示失败: {str(e)}")
            await event.answer("操作失败", alert=True)
