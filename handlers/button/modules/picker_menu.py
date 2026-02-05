"""
选择器菜单模块
处理时间、数字、时长等通用 UI 组件
"""
import logging
from telethon import Button
from ..base import BaseMenu
from services.session_service import session_manager

logger = logging.getLogger(__name__)

class PickerMenu(BaseMenu):
    """选择器菜单"""

    async def show_time_picker(self, event, time_type):
        """显示时间选择器 (已重构：重定向到滚轮)"""
        await self.show_wheel_date_picker(event, time_type)

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
        """显示数字选择器 (已重构：重定向到滚轮)"""
        await self.show_wheel_date_picker(event, side)

    async def show_wheel_date_picker(self, event, side: str):
        """显示高级滚轮式日期选择器"""
        try:
            from services.session_service import session_manager
            import datetime
            import calendar
            
            # 获取当前设置的时间范围
            tr = session_manager.get_time_range(event.chat_id)
            
            # 基础基准时间
            base_date = datetime.datetime.now()
            if not tr.get(f"{side}_year"):
                # 如果未设置，尝试获取会话最早时间作为默认起始值
                earliest, _ = await session_manager.get_chat_message_date_range(event.chat_id)
                if earliest:
                    base_date = earliest
            
            # 获取对应的分量
            y = tr.get(f"{side}_year") or base_date.year
            m = tr.get(f"{side}_month") or base_date.month
            d = tr.get(f"{side}_day") or base_date.day
            h = tr.get(f"{side}_hour") or (base_date.hour if side == "start" else 0)
            mn = tr.get(f"{side}_minute") or (base_date.minute if side == "start" else 0)
            sc = tr.get(f"{side}_second") or (base_date.second if side == "start" else 0)
            
            # 修正日期合法性（比如从31日切到2月）
            _, last_day = calendar.monthrange(y, m if m > 0 else 1)
            if d > last_day: d = last_day
            
            title = "起始" if side == "start" else "结束"
            display_str = f"{y:04d}年{m:02d}月{d:02d}日{h:02d}时{mn:02d}分{sc:02d}秒"
            
            # 构建按钮：三排滚轮模式
            # 1. 增加排
            row_inc = [
                Button.inline("🔼", f"new_menu:picker_adj:{side}:year:1"),
                Button.inline("🔼", f"new_menu:picker_adj:{side}:month:1"),
                Button.inline("🔼", f"new_menu:picker_adj:{side}:day:1"),
                Button.inline("🔼", f"new_menu:picker_adj:{side}:hour:1"),
                Button.inline("🔼", f"new_menu:picker_adj:{side}:minute:1"),
                Button.inline("🔼", f"new_menu:picker_adj:{side}:second:1"),
            ]
            # 2. 数值排
            row_val = [
                Button.inline(f"{y}", "new_menu:noop"),
                Button.inline(f"{m:02d}", "new_menu:noop"),
                Button.inline(f"{d:02d}", "new_menu:noop"),
                Button.inline(f"{h:02d}", "new_menu:noop"),
                Button.inline(f"{mn:02d}", "new_menu:noop"),
                Button.inline(f"{sc:02d}", "new_menu:noop"),
            ]
            # 3. 减少排
            row_dec = [
                Button.inline("🔽", f"new_menu:picker_adj:{side}:year:-1"),
                Button.inline("🔽", f"new_menu:picker_adj:{side}:month:-1"),
                Button.inline("🔽", f"new_menu:picker_adj:{side}:day:-1"),
                Button.inline("🔽", f"new_menu:picker_adj:{side}:hour:-1"),
                Button.inline("🔽", f"new_menu:picker_adj:{side}:minute:-1"),
                Button.inline("🔽", f"new_menu:picker_adj:{side}:second:-1"),
            ]
            
            buttons = [
                row_inc,
                row_val,
                row_dec,
                [Button.inline("♾️ 设为不限", f"new_menu:picker_limit:{side}:none")],
                [Button.inline("✅ 确认选择", "new_menu:history_time_range"), Button.inline("👈 返回", "new_menu:history_time_range")]
            ]
            
            text = (
                f"📅 **{title}时间精细选择 (滚轮模式)**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"当前选中：\n`{display_str}`\n\n"
                f"• 点击 🔼/🔽 微调各项数值\n"
                f"• 自动适配大/小月天数"
            )
            
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"显示滚轮选择器失败: {e}", exc_info=True)
            await event.answer("加载选择器失败", alert=True)

picker_menu = PickerMenu()
