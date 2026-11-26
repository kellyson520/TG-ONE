from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry

import logging

logger = logging.getLogger(__name__)

@MenuHandlerRegistry.register
class HistoryMenuStrategy(BaseMenuHandler):
    """
    Handles History & Time Selection actions:
    - Time Range Picker (Start/End)
    - Date Wheel Picker
    - Day Picker
    - Setting Time Components (Year, Month, Day, Hour, Minute, Second)
    - Saving Time Context
    """

    ACTIONS = {
        # Time Range Selection
        "time_range_selection", "session_dedup_time_range",
        "open_session_time", "open_session_date",
        "select_start_time", "select_end_time",
        "select_days", "day_page",
        "select_year", "select_month", "select_day_of_month",
        "set_time", "set_days", "set_year", "set_month", "set_dom",
        "set_history_year", "set_history_month",
        "set_time_field",
        "open_wheel_picker", "picker_adj", "picker_limit",
        "set_all_time_zero",
        "save_days", "save_time_range",

        # History Task Management
        "history_task_selector", "select_history_task", 
        "select_history_rule", "select_task",
        "current_history_task", "cancel_history_task", "history_task_details",
        "history_time_range", "history_delay_settings",
        "toggle_history_dedup", "history_quick_stats", "history_dry_run",
        "start_history_task", "pause_history_task", "resume_history_task",
        "history_message_filter", "history_filter_media_types",
        "history_filter_media_duration", "history_message_limit",

        # Time Range Presets
        "set_time_range_all", "set_time_range_days",
        "confirm_time_range", "set_start_time", "set_end_time",
        
        # Delay Settings
        "set_delay", "set_history_delay", "set_history_limit", "custom_history_limit",
        
        # Additional Actions
        "history_task_list"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    def _time_owner_id(self, event, session_manager) -> int:
        try:
            context = session_manager.get_time_picker_context(event.chat_id)
        except Exception:
            context = "session"
        return event.sender_id if context == "history" else event.chat_id

    # ------------------------------------------------------------------
    # Main dispatch – delegates to focused helper methods
    # ------------------------------------------------------------------
    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        from handlers.button.new_menu_system import new_menu_system
        from services.session_service import session_manager
        from handlers.button.modules.history import history_module
        from handlers.button.modules.picker_menu import picker_menu

        extra_data = kwargs.get("extra_data", [])
        data = kwargs.get("data", "")
        arg1 = int(extra_data[0]) if extra_data and extra_data[0].isdigit() else 0

        # Build a shared context dict so helpers don't need 8 positional args
        ctx = {
            "event": event,
            "action": action,
            "extra_data": extra_data,
            "data": data,
            "arg1": arg1,
            "menu_controller": menu_controller,
            "new_menu_system": new_menu_system,
            "session_manager": session_manager,
            "history_module": history_module,
            "picker_menu": picker_menu,
        }

        if action in self._CONTEXT_SETUP_ACTIONS:
            await self._handle_context_setup(ctx)
        elif action in self._PICKER_OPEN_ACTIONS:
            await self._handle_picker_open(ctx)
        elif action in self._SET_VALUE_ACTIONS:
            await self._handle_set_values(ctx)
        elif action in self._SAVE_ACTIONS:
            await self._handle_save(ctx)
        elif action in self._TASK_MGMT_ACTIONS:
            await self._handle_task_management(ctx)
        elif action in self._PRESET_ACTIONS:
            await self._handle_presets(ctx)
        elif action in self._DELAY_LIMIT_ACTIONS:
            await self._handle_delay_settings(ctx)

    # ------------------------------------------------------------------
    # Action group membership sets (used by dispatch above)
    # ------------------------------------------------------------------
    _CONTEXT_SETUP_ACTIONS = {"time_range_selection", "session_dedup_time_range"}
    _PICKER_OPEN_ACTIONS = {
        "open_session_time", "open_session_date",
        "select_start_time", "select_end_time",
        "open_wheel_picker", "set_start_time", "set_end_time",
        "select_days", "day_page",
        "select_year", "select_month", "select_day_of_month",
    }
    _SET_VALUE_ACTIONS = {
        "set_time", "set_days", "set_year", "set_month", "set_dom",
        "set_history_year", "set_history_month",
        "set_time_field", "picker_adj", "picker_limit", "set_all_time_zero",
    }
    _SAVE_ACTIONS = {"save_days", "save_time_range"}
    _TASK_MGMT_ACTIONS = {
        "history_task_selector", "select_history_task",
        "select_history_rule", "select_task",
        "current_history_task", "cancel_history_task", "history_task_details",
        "history_time_range", "history_delay_settings",
        "toggle_history_dedup", "history_quick_stats", "history_dry_run",
        "start_history_task", "pause_history_task", "resume_history_task",
        "history_task_list",
    }
    _PRESET_ACTIONS = {"set_time_range_all", "set_time_range_days", "confirm_time_range"}
    _DELAY_LIMIT_ACTIONS = {
        "set_delay", "set_history_delay",
        "set_history_limit", "custom_history_limit",
        "history_message_filter", "history_filter_media_types",
        "history_filter_media_duration", "history_message_limit",
    }

    # ------------------------------------------------------------------
    # 1. Context Setup
    # ------------------------------------------------------------------
    async def _handle_context_setup(self, ctx):
        event = ctx["event"]
        action = ctx["action"]
        sm = ctx["session_manager"]
        nms = ctx["new_menu_system"]

        if action == "time_range_selection":
            sm.set_time_picker_context(event.chat_id, "delete")
            await nms.show_time_range_selection(event)
        elif action == "session_dedup_time_range":
            sm.set_time_picker_context(event.chat_id, "dedup")
            await nms.show_time_range_selection(event)

    # ------------------------------------------------------------------
    # 2. Picker Opening
    # ------------------------------------------------------------------
    async def _handle_picker_open(self, ctx):
        event = ctx["event"]
        action = ctx["action"]
        extra_data = ctx["extra_data"]
        data = ctx["data"]
        sm = ctx["session_manager"]
        nms = ctx["new_menu_system"]
        picker = ctx["picker_menu"]

        if action == "open_session_time":
            try:
                side = extra_data[0]
                unit = extra_data[1]
                unit_map = {
                    "days": "days", "hours": "hours",
                    "minutes": "minutes", "seconds": "seconds"
                }
                await nms.show_single_unit_duration_picker(
                    event, "min" if side == "min" else "max", unit_map[unit]
                )
            except Exception as e:
                logger.error(f"打开会话时间分量选择失败: {str(e)}")
                await event.answer("操作失败", alert=True)

        elif action == "open_session_date":
            try:
                side = extra_data[0] if extra_data else "start"
                await nms.show_wheel_date_picker(event, side)
            except Exception as e:
                logger.error(f"打开滚轮日期选择器失败: {str(e)}")
                await event.answer("操作失败", alert=True)

        elif action == "select_start_time":
            await nms.show_wheel_date_picker(event, "start")

        elif action == "select_end_time":
            await nms.show_wheel_date_picker(event, "end")

        elif action == "open_wheel_picker":
            await picker.show_wheel_date_picker(event, extra_data[0])

        elif action == "set_start_time":
            sm.set_time_picker_context(event.chat_id, "history")
            await picker.show_wheel_date_picker(event, "start")

        elif action == "set_end_time":
            sm.set_time_picker_context(event.chat_id, "history")
            await picker.show_wheel_date_picker(event, "end")

        elif action == "select_days":
            if extra_data and extra_data[0] == "history":
                sm.set_time_picker_context(event.chat_id, "history")
            await nms.show_day_picker(event)

        elif action == "day_page":
            await nms.show_day_picker(event)

        elif action in ("select_year", "select_month", "select_day_of_month"):
            try:
                extra_context = data.split(":")[-1] if ":" in data else ""
                side = "start" if "start" in extra_context else "end"
                await nms.show_wheel_date_picker(event, side)
            except Exception as e:
                logger.error(f"打开滚轮选择器失败: {str(e)}")
                await nms.show_time_range_selection(event)

    # ------------------------------------------------------------------
    # 3. Setting Values
    # ------------------------------------------------------------------
    async def _handle_set_values(self, ctx):
        event = ctx["event"]
        action = ctx["action"]
        extra_data = ctx["extra_data"]
        arg1 = ctx["arg1"]
        sm = ctx["session_manager"]
        mc = ctx["menu_controller"]
        nms = ctx["new_menu_system"]
        hm = ctx["history_module"]
        picker = ctx["picker_menu"]

        if action == "set_time":
            try:
                owner_id = self._time_owner_id(event, sm)
                time_type = extra_data[0]
                unit = extra_data[1]
                value = int(extra_data[2])
                await sm.set_time_component(owner_id, time_type, unit, value)
                if time_type == "start":
                    await hm.show_start_time_menu(event)
                else:
                    await hm.show_end_time_menu(event)
            except Exception as e:
                logger.error(f"设置时间失败: {str(e)}")
                await event.answer("操作失败", alert=True)

        elif action == "set_days":
            await sm.set_days(self._time_owner_id(event, sm), arg1)
            await nms.show_time_range_selection(event)

        elif action == "set_year":
            await sm.set_year(self._time_owner_id(event, sm), arg1)
            await event.answer("✅ 已设置年份")
            await mc.show_history_time_range(event)

        elif action == "set_month":
            await sm.set_month(self._time_owner_id(event, sm), arg1)
            await event.answer("✅ 已设置月份")
            await mc.show_history_time_range(event)

        elif action == "set_dom":
            await sm.set_day_of_month(self._time_owner_id(event, sm), arg1)
            await event.answer("✅ 已设置日期")
            await mc.show_history_time_range(event)

        elif action == "set_history_year":
            await sm.set_year(event.sender_id, arg1)
            await event.answer(f"✅ 已设置年份: {arg1 if arg1 > 0 else '不限'}")
            await mc.show_history_time_range(event)

        elif action == "set_history_month":
            await sm.set_month(event.sender_id, arg1)
            await event.answer(f"✅ 已设置月份: {arg1 if arg1 > 0 else '不限'}月")
            await mc.show_history_time_range(event)

        elif action == "set_time_field":
            await self._handle_set_time_field(event, extra_data, sm, nms)

        elif action == "picker_adj":
            try:
                side = extra_data[0]
                field = extra_data[1]
                delta = int(extra_data[2])
                await sm.adjust_time_component(self._time_owner_id(event, sm), side, field, delta)
                await picker.show_wheel_date_picker(event, side)
            except Exception as e:
                logger.error(f"调整时间分量失败: {e}")
                await event.answer("调整失败", alert=True)

        elif action == "picker_limit":
            try:
                side = extra_data[0]
                owner_id = self._time_owner_id(event, sm)
                tr = sm.get_time_range(owner_id)
                prefix = f"{side}_"
                for k in ("year", "month", "day", "hour", "minute", "second"):
                    tr[prefix + k] = 0
                sm.set_time_range(owner_id, tr)
                await event.answer("✅ 已设为不限")
                await picker.show_wheel_date_picker(event, side)
            except Exception as e:
                logger.error(f"重置时间限制失败: {e}")
                await event.answer("操作失败", alert=True)

        elif action == "set_all_time_zero":
            owner_id = self._time_owner_id(event, sm)
            for side in ("start", "end"):
                for field in ("year", "month", "day", "hour", "minute", "second"):
                    await sm.set_time_field(owner_id, side, field, 0)
            await event.answer("✅ 已重置为全部时间")
            await hm.show_time_range_selection(event)

    async def _handle_set_time_field(self, event, extra_data, sm, nms):
        """Handle the set_time_field action."""
        try:
            if len(extra_data) >= 3:
                side = extra_data[0]
                field = extra_data[1]
                value = int(extra_data[2])
                await sm.set_time_field(
                    self._time_owner_id(event, sm), side, field, value
                )
                await event.answer("✅ 设置已更新")
                await nms.show_wheel_date_picker(event, side)
            else:
                await event.answer("参数不足", alert=True)
        except Exception as e:
            logger.error(f"设置时间字段失败: {str(e)}")
            await event.answer("操作失败", alert=True)

    # ------------------------------------------------------------------
    # 4. Save
    # ------------------------------------------------------------------
    async def _handle_save(self, ctx):
        event = ctx["event"]
        action = ctx["action"]
        sm = ctx["session_manager"]
        nms = ctx["new_menu_system"]

        if action == "save_days":
            await nms.show_time_range_selection(event)
        elif action == "save_time_range":
            success = await sm.save_time_range_settings(
                self._time_owner_id(event, sm)
            )
            if success:
                await event.answer("✅ 时间范围设置已保存")
                await nms.show_time_range_selection(event)
            else:
                await event.answer("❌ 保存失败")

    # ------------------------------------------------------------------
    # 5. History Task Management
    # ------------------------------------------------------------------
    async def _handle_task_management(self, ctx):
        event = ctx["event"]
        action = ctx["action"]
        arg1 = ctx["arg1"]
        sm = ctx["session_manager"]
        mc = ctx["menu_controller"]
        nms = ctx["new_menu_system"]

        if action in ("history_task_selector", "select_history_task"):
            await mc.show_history_task_selector(event)

        elif action == "history_task_list":
            page = arg1 if arg1 > 0 else 1
            await mc.show_history_task_list(event, page=page)

        elif action in ("select_history_rule", "select_task"):
            rule_id = arg1
            res = await sm.set_selected_rule(event.sender_id, rule_id)
            if res.get('success'):
                await event.answer(f"✅ 已选择规则 #{rule_id}")
                await mc.show_history_task_actions(event)
            else:
                await event.answer(f"❌ 选择失败: {res.get('error')}", alert=True)

        elif action == "current_history_task":
            await mc.show_current_history_task(event)

        elif action == "cancel_history_task":
            await mc.cancel_history_task(event)

        elif action == "history_task_details":
            await event.answer("📊 任务详情功能开发中", alert=True)

        elif action == "history_time_range":
            sm.set_time_picker_context(event.chat_id, "history")
            await mc.show_history_time_range(event)

        elif action == "history_delay_settings":
            await nms.show_history_delay_settings(event)

        elif action == "toggle_history_dedup":
            await mc.toggle_history_dedup(event)

        elif action == "history_quick_stats":
            await mc.show_quick_stats(event)

        elif action == "history_dry_run":
            await mc.start_dry_run(event)

        elif action == "start_history_task":
            await mc.start_history_task(event)

        elif action == "pause_history_task":
            await mc.pause_history_task(event)

        elif action == "resume_history_task":
            await mc.resume_history_task(event)

    # ------------------------------------------------------------------
    # 6. Time Range Presets
    # ------------------------------------------------------------------
    async def _handle_presets(self, ctx):
        event = ctx["event"]
        action = ctx["action"]
        arg1 = ctx["arg1"]
        sm = ctx["session_manager"]
        mc = ctx["menu_controller"]
        nms = ctx["new_menu_system"]

        if action == "set_time_range_all":
            context = sm.get_time_picker_context(event.chat_id)
            owner_id = self._time_owner_id(event, sm)
            tr = sm.get_time_range(owner_id)
            for prefix in ("start_", "end_"):
                for k in ("year", "month", "day", "hour", "minute", "second"):
                    tr[prefix + k] = 0
            sm.set_time_range(owner_id, tr)
            await event.answer("✅ 已设为全部历史")
            if context == "history":
                await mc.show_history_time_range(event)
            else:
                await nms.show_time_range_selection(event)

        elif action == "set_time_range_days":
            days = arg1
            from datetime import datetime, timedelta
            now = datetime.now()
            start = now - timedelta(days=days)
            context = sm.get_time_picker_context(event.chat_id)
            owner_id = self._time_owner_id(event, sm)
            tr = sm.get_time_range(owner_id)
            tr["start_year"] = start.year
            tr["start_month"] = start.month
            tr["start_day"] = start.day
            tr["end_year"] = now.year
            tr["end_month"] = now.month
            tr["end_day"] = now.day
            sm.set_time_range(owner_id, tr)
            await event.answer(f"✅ 已设为最近{days}天")
            if context == "history":
                await mc.show_history_time_range(event)
            else:
                await nms.show_time_range_selection(event)

        elif action == "confirm_time_range":
            await event.answer("✅ 时间范围已确认")
            await mc.show_history_task_actions(event)

    # ------------------------------------------------------------------
    # 7. Delay & Limit Settings
    # ------------------------------------------------------------------
    async def _handle_delay_settings(self, ctx):
        event = ctx["event"]
        action = ctx["action"]
        arg1 = ctx["arg1"]
        sm = ctx["session_manager"]
        mc = ctx["menu_controller"]
        hm = ctx["history_module"]

        if action in ("set_delay", "set_history_delay"):
            delay = arg1
            await sm.update_delay_setting(event.sender_id, delay)
            await event.answer(f"✅ 已设置延迟: {delay}秒")
            await mc.show_history_task_actions(event)

        elif action == "set_history_limit":
            limit = arg1
            res = await sm.set_history_message_limit(limit)
            if not res.get("success"):
                await event.answer(f"❌ {res.get('error', '设置失败')}", alert=True)
                return
            await event.answer(f"✅ 已设置数量限制: {limit if limit > 0 else '不限'}")
            await hm.show_message_limit_menu(event)

        elif action == "custom_history_limit":
            await sm.update_user_state(
                event.sender_id,
                event.chat_id,
                "set_history_limit",
                None,
                {"state_type": "history"},
            )
            await event.answer("🔢 请在对话框输入消息数量限制数值", alert=True)

        elif action == "history_message_filter":
            await hm.show_message_filter_menu(event)

        elif action == "history_filter_media_types":
            await hm.show_media_types(event)

        elif action == "history_filter_media_duration":
            await hm.show_media_duration_settings(event)

        elif action == "history_message_limit":
            await hm.show_message_limit_menu(event)
