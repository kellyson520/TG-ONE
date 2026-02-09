from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from core.container import container
from telethon import Button
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
        "save_days", "save_time_range"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        from handlers.button.new_menu_system import new_menu_system
        from services.session_service import session_manager
        from handlers.button.modules.history import history_module
        from handlers.button.modules.picker_menu import picker_menu

        extra_data = kwargs.get("extra_data", [])
        data = kwargs.get("data", "")
        # Helper to get first int arg safely
        arg1 = int(extra_data[0]) if extra_data and extra_data[0].isdigit() else 0

        # 1. Context Setup
        if action == "time_range_selection":
            session_manager.set_time_picker_context(event.chat_id, "delete")
            await new_menu_system.show_time_range_selection(event)
        
        elif action == "session_dedup_time_range":
            session_manager.set_time_picker_context(event.chat_id, "dedup")
            await new_menu_system.show_time_range_selection(event)

        # 2. Picker Opening
        elif action == "open_session_time":
            try:
                side = extra_data[0]
                unit = extra_data[1]
                unit_map = {
                    "days": "days", "hours": "hours",
                    "minutes": "minutes", "seconds": "seconds"
                }
                await new_menu_system.show_single_unit_duration_picker(
                    event, "min" if side == "min" else "max", unit_map[unit]
                )
            except Exception as e:
                logger.error(f"打开会话时间分量选择失败: {str(e)}")
                await event.answer("操作失败", alert=True)

        elif action == "open_session_date":
            # 统一使用高级滚轮选择器
            try:
                side = extra_data[0] if extra_data else "start"
                await new_menu_system.show_wheel_date_picker(event, side)
            except Exception as e:
                logger.error(f"打开滚轮日期选择器失败: {str(e)}")
                await event.answer("操作失败", alert=True)

        elif action == "select_start_time":
            await new_menu_system.show_wheel_date_picker(event, "start")

        elif action == "select_end_time":
            await new_menu_system.show_wheel_date_picker(event, "end")

        elif action == "open_wheel_picker":
            await picker_menu.show_wheel_date_picker(event, extra_data[0])

        elif action == "select_days":
             if extra_data and extra_data[0] == "history":
                  session_manager.set_time_picker_context(event.chat_id, "history")
             await new_menu_system.show_day_picker(event)

        elif action == "day_page":
             await new_menu_system.show_day_picker(event)

        elif action in ["select_year", "select_month", "select_day_of_month"]:
            try:
                extra_context = data.split(":")[-1] if ":" in data else ""
                side = "start" if "start" in extra_context else "end"
                await new_menu_system.show_wheel_date_picker(event, side)
            except Exception as e:
                 logger.error(f"打开滚轮选择器失败: {str(e)}")
                 await new_menu_system.show_time_range_selection(event)

        # 3. Setting Values
        elif action == "set_time":
            # new_menu:set_time:{start|end}:{hour|minute}:{val}
            try:
                time_type = extra_data[0]
                unit = extra_data[1]
                value = int(extra_data[2])
                await session_manager.set_time_component(
                    event.chat_id, time_type, unit, value
                )
                if time_type == "start":
                    await history_module.show_start_time_menu(event)
                else:
                    await history_module.show_end_time_menu(event)
            except Exception as e:
                logger.error(f"设置时间失败: {str(e)}")
                await event.answer("操作失败", alert=True)

        elif action == "set_days":
             days = arg1
             await session_manager.set_days(event.chat_id, days)
             await new_menu_system.show_time_range_selection(event)

        elif action == "set_year":
             year = arg1
             await session_manager.set_year(event.chat_id, year)
             await event.answer("✅ 已设置年份")
             await menu_controller.show_history_time_range(event)

        elif action == "set_month":
             month = arg1
             await session_manager.set_month(event.chat_id, month)
             await event.answer("✅ 已设置月份")
             await menu_controller.show_history_time_range(event)

        elif action == "set_dom":
             dom = arg1
             await session_manager.set_day_of_month(event.chat_id, dom)
             await event.answer("✅ 已设置日期")
             await menu_controller.show_history_time_range(event)

        elif action == "set_history_year":
             year = arg1
             await session_manager.set_year(event.chat_id, year)
             await event.answer(f"✅ 已设置年份: {year if year > 0 else '不限'}")
             await menu_controller.show_history_time_range(event)

        elif action == "set_history_month":
             month = arg1
             await session_manager.set_month(event.chat_id, month)
             await event.answer(f"✅ 已设置月份: {month if month > 0 else '不限'}月")
             await menu_controller.show_history_time_range(event)

        elif action == "set_time_field":
            try:
                if len(extra_data) >= 3:
                    side = extra_data[0]
                    field = extra_data[1]
                    value = int(extra_data[2])
                    
                    await session_manager.set_time_field(
                        event.chat_id, side, field, value
                    )
                    
                    # Feedback logic from original code
                    # ... (Simplified for brevity, assuming standard toast)
                    await event.answer("✅ 设置已更新")
                    
                    # Return to wheel picker
                    await new_menu_system.show_wheel_date_picker(event, side)
                else:
                    await event.answer("参数不足", alert=True)
            except Exception as e:
                logger.error(f"设置时间字段失败: {str(e)}")
                await event.answer("操作失败", alert=True)

        elif action == "picker_adj":
            try:
                side = extra_data[0]
                field = extra_data[1]
                delta = int(extra_data[2])
                await session_manager.adjust_time_component(event.chat_id, side, field, delta)
                await picker_menu.show_wheel_date_picker(event, side)
            except Exception as e:
                logger.error(f"调整时间分量失败: {e}")
                await event.answer("调整失败", alert=True)

        elif action == "picker_limit":
            try:
                side = extra_data[0]
                # logic to reset fields to 0
                tr = session_manager.get_time_range(event.chat_id)
                prefix = f"{side}_"
                for k in ["year", "month", "day", "hour", "minute", "second"]:
                    tr[prefix + k] = 0
                session_manager.set_time_range(event.chat_id, tr)
                await event.answer("✅ 已设为不限")
                await picker_menu.show_wheel_date_picker(event, side)
            except Exception as e:
                logger.error(f"重置时间限制失败: {e}")
                await event.answer("操作失败", alert=True)

        elif action == "set_all_time_zero":
             # reset all components to 0
             for side in ["start", "end"]:
                 for field in ["year", "month", "day", "seconds"]:
                     await session_manager.set_time_field(event.chat_id, side, field, 0)
             await event.answer("✅ 已重置为全部时间")
             await history_module.show_time_range_selection(event)

        # 4. Save
        elif action == "save_days":
             await new_menu_system.show_time_range_selection(event)

        elif action == "save_time_range":
             success = await session_manager.save_time_range_settings(event.chat_id)
             if success:
                 await event.answer("✅ 时间范围设置已保存")
                 await new_menu_system.show_time_range_selection(event)
             else:
                 await event.answer("❌ 保存失败")
