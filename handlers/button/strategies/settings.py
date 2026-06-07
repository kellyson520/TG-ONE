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
        "media_duration_settings", "open_duration_picker",
        "pick_duration_unit", "confirm_duration_value",
        "save_duration_settings",
        "toggle_media_size_filter", "toggle_media_size_alert",
        # Aliases and Navigation
        "allow_text", "filter_allow_text", "toggle_allow_text", "history_toggle_allow_text",
        "toggle_media_extension", "filter_media_extension",
        "filter_media_size", "filter_media_duration",
        "set_media_size_limit", "toggle_ext", "media_extensions",
        "save_message_filter",
        "toggle_allow_emoji", "toggle_dedup_enabled", "toggle_dedup_mode",
        "filter_settings", "media_types", "message_filter", "filter_media_types",
        "history_toggle_image", "toggle_image",
        "history_toggle_video", "toggle_video",
        "history_toggle_music", "toggle_music",
        "history_toggle_voice", "toggle_voice",
        "history_toggle_document", "toggle_document",
        
        # Dedup Time Window Settings
        "toggle_time_window", "set_time_window",
        "toggle_similarity", "set_similarity",
        "toggle_content_hash",
        
        # Performance Monitoring
        "db_performance_refresh", "detailed_performance", "performance_tuning",
        
        # Misc
        "create_rule"
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

        elif action == "media_duration_settings":
            await new_menu_system.show_media_duration_settings(event)

        elif action == "open_duration_picker":
            side = extra_data[0] if len(extra_data) > 0 else "min"
            unit = extra_data[1] if len(extra_data) > 1 else "seconds"
            current_value = await self._get_duration_component(side, unit)
            await new_menu_system.show_single_unit_duration_picker(event, side, unit, current_value)

        elif action == "pick_duration_unit":
            if len(extra_data) < 3:
                await event.answer("参数不足", alert=True)
                return
            side, unit, value = extra_data[0], extra_data[1], int(extra_data[2])
            await self._set_duration_component(side, unit, value)
            await event.answer("✅ 已更新时长")
            await new_menu_system.show_single_unit_duration_picker(event, side, unit, value)

        elif action == "confirm_duration_value":
            await event.answer("✅ 时长设置已保存")
            await new_menu_system.show_media_duration_settings(event)

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

        elif action == "media_extensions":
            await new_menu_system.show_media_extension_settings(event)
            
        elif action == "filter_media_size":
            await new_menu_system.show_media_size_settings(event)

        elif action == "set_media_size_limit":
            await self._handle_set_media_size_limit(event, extra_data)

        elif action == "toggle_ext":
            if not extra_data:
                await event.answer("参数不足", alert=True)
                return
            ok = await forward_settings_service.toggle_media_extension(extra_data[0])
            await event.answer("✅ 已更新扩展名" if ok is not None else "操作失败")
            await new_menu_system.show_media_extension_settings(event)
        
        elif action == "filter_media_duration":
             await new_menu_system.show_media_duration_settings(event)

        elif action == "save_message_filter":
            # 占位：此处可落库保存筛选配置，当前仅提示成功并返回
            try:
                await event.answer("✅ 已保存筛选配置")
            except Exception as e:
                logger.warning(f"保存筛选配置提示发送失败: {e}")
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
        
        # Dedup Time Window Settings
        elif action == "toggle_time_window":
            # toggle_time_window:{true|false}
            enabled = extra_data[0] if extra_data else "true"
            enabled_bool = enabled.lower() in ["true", "1", "yes"]
            from services.dedup_service import dedup_service
            await dedup_service.set_time_window_enabled(enabled_bool)
            await event.answer(f"✅ 去重时间窗口已{'开启' if enabled_bool else '关闭'}")
            from controllers.menu_controller import menu_controller
            await menu_controller.show_dedup_config(event)
        
        elif action == "set_time_window":
            # set_time_window:{hours}
            hours = int(extra_data[0]) if extra_data else 24
            from services.dedup_service import dedup_service
            await dedup_service.set_time_window_hours(hours)
            window_text = "永久" if hours == 0 else f"{hours}小时"
            await event.answer(f"✅ 时间窗口已设为 {window_text}")
            from controllers.menu_controller import menu_controller
            await menu_controller.show_dedup_config(event)
        
        elif action == "toggle_similarity":
            # toggle_similarity:{true|false}
            enabled = extra_data[0] if extra_data else "true"
            enabled_bool = enabled.lower() in ["true", "1", "yes"]
            from services.dedup_service import dedup_service
            await dedup_service.toggle_feature("smart_similarity", enabled_bool)
            await event.answer(f"✅ 智能相似度检测已{'开启' if enabled_bool else '关闭'}")
            from handlers.button.modules.smart_dedup_menu import smart_dedup_menu
            await smart_dedup_menu.show_dedup_similarity(event)
        
        elif action == "set_similarity":
            # set_similarity:{threshold}
            threshold = float(extra_data[0]) if extra_data else 0.85
            from services.dedup_service import dedup_service
            await dedup_service.set_similarity_threshold(threshold)
            await event.answer(f"✅ 相似度阈值已设为 {threshold:.0%}")
            from handlers.button.modules.smart_dedup_menu import smart_dedup_menu
            await smart_dedup_menu.show_dedup_similarity(event)
        
        elif action == "toggle_content_hash":
            # toggle_content_hash:{true|false}
            enabled = extra_data[0] if extra_data else "true"
            enabled_bool = enabled.lower() in ["true", "1", "yes"]
            from services.dedup_service import dedup_service
            await dedup_service.toggle_feature("content_hash", enabled_bool)
            await event.answer(f"✅ 内容哈希去重已{'开启' if enabled_bool else '关闭'}")
            from handlers.button.modules.smart_dedup_menu import smart_dedup_menu
            await smart_dedup_menu.show_dedup_content_hash(event)
        
        # Performance Monitoring
        elif action == "db_performance_refresh":
            from controllers.menu_controller import menu_controller
            await menu_controller.show_db_performance_monitor(event)
            await event.answer("✅ 数据库性能面板已刷新")
        
        elif action == "detailed_performance":
            from controllers.menu_controller import menu_controller
            await menu_controller.show_performance_analysis(event)
        
        elif action == "performance_tuning":
            from controllers.menu_controller import menu_controller
            await menu_controller.show_db_optimization_center(event)
        
        # Misc
        elif action == "create_rule":
            from controllers.menu_controller import menu_controller
            await menu_controller.enter_create_rule_state(event)

    # --- Internal Handlers (Migrated from menu_entrypoint.py) ---

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

    async def _handle_set_media_size_limit(self, event, extra_data):
        from services.forward_settings_service import forward_settings_service
        from handlers.button.new_menu_system import new_menu_system
        if extra_data:
            try:
                limit_mb = max(1, int(extra_data[0]))
            except (TypeError, ValueError):
                await event.answer("大小参数无效", alert=True)
                return
            ok = await forward_settings_service.set_media_size_limit(limit_mb)
            await event.answer(f"✅ 大小限制已设为 {limit_mb}MB" if ok else "操作失败", alert=not ok)
            await new_menu_system.show_media_size_settings(event)
            return

        buttons = [
            [
                Button.inline("10MB", "new_menu:set_media_size_limit:10"),
                Button.inline("50MB", "new_menu:set_media_size_limit:50"),
                Button.inline("100MB", "new_menu:set_media_size_limit:100"),
            ],
            [
                Button.inline("200MB", "new_menu:set_media_size_limit:200"),
                Button.inline("500MB", "new_menu:set_media_size_limit:500"),
                Button.inline("1GB", "new_menu:set_media_size_limit:1024"),
            ],
            [Button.inline("👈 返回", "new_menu:filter_media_size")],
        ]
        await event.edit("📐 **媒体大小限制**\n\n请选择最大允许文件大小：", buttons=buttons)

    def _duration_key(self, side: str) -> str:
        return "duration_min_seconds" if side == "min" else "duration_max_seconds"

    def _seconds_to_duration_parts(self, total: int) -> dict:
        total = max(0, int(total or 0))
        return {
            "days": total // 86400,
            "hours": (total % 86400) // 3600,
            "minutes": (total % 3600) // 60,
            "seconds": total % 60,
        }

    def _duration_parts_to_seconds(self, parts: dict) -> int:
        return (
            int(parts.get("days", 0)) * 86400
            + int(parts.get("hours", 0)) * 3600
            + int(parts.get("minutes", 0)) * 60
            + int(parts.get("seconds", 0))
        )

    async def _get_duration_component(self, side: str, unit: str) -> int:
        from services.forward_settings_service import forward_settings_service
        settings = await forward_settings_service.get_global_media_settings()
        parts = self._seconds_to_duration_parts(settings.get(self._duration_key(side), 0))
        return int(parts.get(unit, 0))

    async def _set_duration_component(self, side: str, unit: str, value: int) -> None:
        from services.forward_settings_service import forward_settings_service
        settings = await forward_settings_service.get_global_media_settings()
        key = self._duration_key(side)
        parts = self._seconds_to_duration_parts(settings.get(key, 0))
        parts[unit] = max(0, int(value))
        await forward_settings_service.update_global_media_setting(
            key,
            self._duration_parts_to_seconds(parts),
        )
