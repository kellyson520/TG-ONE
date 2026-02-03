"""
选择器菜单模块
处理时间、数字、时长等通用 UI 组件
"""
import logging
from telethon import Button
from ..base import BaseMenu
from ..session_management import session_manager

logger = logging.getLogger(__name__)

class PickerMenu(BaseMenu):
    """选择器菜单"""

    async def show_time_picker(self, event, time_type):
        """显示时间选择器"""
        hours = list(range(24))
        minutes = [0, 15, 30, 45]
        buttons = []
        hour_buttons = []
        for i, hour in enumerate(hours):
            if i % 6 == 0 and hour_buttons:
                buttons.append(hour_buttons)
                hour_buttons = []
            hour_buttons.append(Button.inline(f"{hour:02d}h", f"new_menu:set_time:{time_type}:hour:{hour}"))
        if hour_buttons: buttons.append(hour_buttons)

        minute_buttons = [Button.inline(f"{minute:02d}m", f"new_menu:set_time:{time_type}:minute:{minute}") for minute in minutes]
        buttons.append(minute_buttons)
        buttons.append([Button.inline("👈 返回上一级", "new_menu:time_range_selection")])
        await self._render_from_text(event, f"🕐 **选择{'起始' if time_type == 'start' else '结束'}时间**\n\n请选择小时和分钟：", buttons)

    async def show_day_picker(self, event):
        """显示天数选择器"""
        buttons = []
        day_buttons = []
        for day in range(32):
            if day % 8 == 0 and day_buttons:
                buttons.append(day_buttons)
                day_buttons = []
            day_buttons.append(Button.inline(f"{day}天", f"new_menu:set_days:{day}"))
        if day_buttons: buttons.append(day_buttons)

        try: ctx = session_manager.get_time_picker_context(event.chat_id)
        except: ctx = "session"
        back_action = "new_menu:history_time_range" if ctx == "history" else "new_menu:time_range_selection"
        buttons.extend([
            [Button.inline("⬅️ 上一页", "new_menu:day_page:prev"), Button.inline("下一页 ➡️", "new_menu:day_page:next")],
            [Button.inline("💾 保存", "new_menu:save_days"), Button.inline("❌ 取消", back_action)],
            [Button.inline("👈 返回上一级", back_action)],
        ])
        await self._render_from_text(event, "📅 **选择天数 (0-31)**\n\n请选择天数：", buttons)

    async def show_single_unit_duration_picker(self, event, side: str, unit: str, selected_value: int = None):
        """显示单单位时长选择器 (天/时/分/秒)"""
        try:
            # 这里的逻辑在 new_menu_system.py 中大约在 1940 行开始
            current_val = selected_value if selected_value is not None else 0
            # 常见预设值
            presets = {
                "days": [0, 1, 2, 3, 7, 14, 30],
                "hours": [0, 1, 2, 3, 6, 12, 18],
                "minutes": [0, 1, 5, 10, 15, 30, 45],
                "seconds": [0, 5, 10, 20, 30, 40, 50],
            }.get(unit, list(range(0, 60, 10)))
            
            buttons = []
            row = []
            for v in presets:
                label = f"{v} {'✅' if v == current_val else ''}"
                row.append(Button.inline(label, f"new_menu:pick_duration_unit:{side}:{unit}:{v}"))
                if len(row) == 4:
                    buttons.append(row)
                    row = []
            if row: buttons.append(row)
            
            buttons.append([
                Button.inline("✓ 保存", f"new_menu:confirm_duration_value:{side}:{unit}:{current_val}"),
                Button.inline("👈 返回", "new_menu:media_duration_settings"),
            ])
            unit_label = {"days":"天", "hours":"时", "minutes":"分", "seconds":"秒"}.get(unit, unit)
            title = "起始" if side == "min" else "终止"
            await self._render_from_text(event, f"⏰ **{title}{unit_label}**\n\n请选择数值，点击✓保存：", buttons)
        except Exception as e:
            logger.error(f"显示分量选择器失败: {str(e)}")
            await event.answer("操作失败", alert=True)

    async def show_duration_range_picker(self, event, side: str):
        """显示时长范围单位选择器 (天/时/分/秒的分流菜单)"""
        try:
            buttons = [
                [Button.inline("📅 设置天数", f"new_menu:open_duration_picker:{side}:days")],
                [Button.inline("🕐 设置小时", f"new_menu:open_duration_picker:{side}:hours")],
                [Button.inline("⏲️ 设置分钟", f"new_menu:open_duration_picker:{side}:minutes")],
                [Button.inline("⏱️ 设置秒数", f"new_menu:open_duration_picker:{side}:seconds")],
                [Button.inline("👈 返回上一级", "new_menu:media_duration_settings")],
            ]
            title = "起始" if side == "min" else "终止"
            await self._render_from_text(event, f"⏰ **{title}时长单位选择**\n\n请选择要设置的时间单位：", buttons)
        except Exception as e:
            logger.error(f"显示时长范围单位选择器失败: {str(e)}")
            await event.answer("操作失败", alert=True)

    async def show_session_numeric_picker(self, event, side: str, field: str):
        """显示会话管理的数字选择器 (年/月/日)"""
        import datetime
        current_year = datetime.datetime.now().year
        
        buttons = []
        if field == "year":
            # 过去5年 + 未来1年
            row = []
            for y in range(current_year - 5, current_year + 2):
                row.append(Button.inline(f"{y}", f"new_menu:set_time_field:{side}:year:{y}"))
                if len(row) == 4: buttons.append(row); row = []
            if row: buttons.append(row)
        elif field == "month":
            row = []
            for m in range(1, 13):
                row.append(Button.inline(f"{m}月", f"new_menu:set_time_field:{side}:month:{m}"))
                if len(row) == 4: buttons.append(row); row = []
            if row: buttons.append(row)
        elif field == "day":
             # 简单的 1-31
            row = []
            for d in range(1, 32):
                row.append(Button.inline(f"{d}", f"new_menu:set_time_field:{side}:day:{d}"))
                if len(row) == 6: buttons.append(row); row = []
            if row: buttons.append(row)
            
        buttons.append([Button.inline("♾️ 重置为不限", "new_menu:set_all_time_zero")])
        buttons.append([Button.inline("👈 返回上一级", "new_menu:time_range_selection")])
        
        field_name = {"year": "年份", "month": "月份", "day": "日期"}.get(field, field)
        title = "起始" if side == "start" else "结束"
        await self._render_from_text(event, f"📅 **选择{title}{field_name}**", buttons)

picker_menu = PickerMenu()
