from datetime import datetime

import logging
import os
from telethon import Button

from handlers.button.forward_management import forward_manager
from services.session_service import session_manager

from ..base import BaseMenu

logger = logging.getLogger(__name__)


class HistoryModule(BaseMenu):
    async def show_numeric_picker(self, event, side: str, field: str):
        """通用数字选择器（年份/月/日/时分秒）
        side: start|end, field: year|month|day|hour|minute|second
        """
        try:
            buttons = []
            side = "start" if side == "start" else "end"

            if field == "year":
                # 基于消息范围动态生成年份
                earliest_date, latest_date = (
                    await session_manager.get_chat_message_date_range(event.chat_id)
                )
                current_year = datetime.now().year
                if earliest_date and latest_date:
                    years = list(range(earliest_date.year, latest_date.year + 1))
                    years.insert(0, 0)
                else:
                    years = [0] + list(range(current_year - 5, current_year + 1))
                row = []
                for y in years:
                    label = f"{y}年" if y > 0 else "不限"
                    row.append(
                        Button.inline(label, f"new_menu:set_time_field:{side}:year:{y}")
                    )
                    if len(row) == 4:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)

            elif field == "month":
                months = [0] + list(range(1, 13))
                names = [
                    "不限",
                    "1月",
                    "2月",
                    "3月",
                    "4月",
                    "5月",
                    "6月",
                    "7月",
                    "8月",
                    "9月",
                    "10月",
                    "11月",
                    "12月",
                ]
                row = []
                for i, m in enumerate(months):
                    row.append(
                        Button.inline(
                            names[i], f"new_menu:set_time_field:{side}:month:{m}"
                        )
                    )
                    if len(row) == 4:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)

            elif field == "day":
                days = list(range(0, 32))
                row = []
                for d in days:
                    label = f"{d}日" if d > 0 else "不限"
                    row.append(
                        Button.inline(label, f"new_menu:set_time_field:{side}:day:{d}")
                    )
                    if len(row) == 8:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)

            elif field in ["hour", "minute", "second"]:
                if field == "hour":
                    values = list(range(0, 24))
                    unit = "时"
                    multiplier = 3600
                elif field == "minute":
                    values = list(range(0, 60, 5))
                    unit = "分"
                    multiplier = 60
                else:
                    values = list(range(0, 60, 5))
                    unit = "秒"
                    multiplier = 1
                row = []
                for v in values:
                    seconds = v * multiplier
                    row.append(
                        Button.inline(
                            f"{v}{unit}",
                            f"new_menu:set_time_field:{side}:seconds:{seconds}",
                        )
                    )
                    if len(row) == 6:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)

            # 返回上一页
            buttons.append(
                [Button.inline("👈 返回上一级", "new_menu:history_time_range")]
            )

            side_text = "起始" if side == "start" else "结束"
            title_map = {
                "year": "年份",
                "month": "月份",
                "day": "日期",
                "hour": "小时",
                "minute": "分钟",
                "second": "秒数",
            }
            text = f"📅 请选择{side_text}{title_map.get(field, field)}："

            # 使用安全编辑避免 MessageNotModifiedError
            try:
                from utils.telegram_utils import safe_edit

                await safe_edit(event, text, buttons)
            except Exception as edit_error:
                # 如果安全编辑失败，尝试发送新消息
                logger.warning(f"安全编辑失败，发送新消息: {edit_error}")
                await event.respond(text, buttons=buttons)
        except Exception as e:
            logger.error(f"显示数字选择器失败: {e}")
            await event.answer("操作失败", alert=True)

    async def show_time_range_selection(self, event):
        session_manager.set_time_picker_context(event.chat_id, "history")
        try:
            earliest_date, latest_date = (
                await session_manager.get_chat_message_date_range(event.chat_id)
            )
            date_range_text = ""
            if earliest_date and latest_date:
                date_range_text = f"📊 消息范围: {earliest_date.strftime('%Y年%m月%d日')} - {latest_date.strftime('%Y年%m月%d日')}\n"
        except Exception:
            date_range_text = ""

        try:
            display = await session_manager.get_time_range_display(event.chat_id)
        except Exception:
            display = "0天 00:00:00 - ∞"

        buttons = [
            [
                Button.inline("起始年", "new_menu:open_history_time:start:year"),
                Button.inline("月", "new_menu:open_history_time:start:month"),
                Button.inline("日", "new_menu:open_history_time:start:day"),
            ],
            [
                Button.inline("起始时", "new_menu:open_history_time:start:hour"),
                Button.inline("分", "new_menu:open_history_time:start:minute"),
                Button.inline("秒", "new_menu:open_history_time:start:second"),
            ],
            [
                Button.inline("结束年", "new_menu:open_history_time:end:year"),
                Button.inline("月", "new_menu:open_history_time:end:month"),
                Button.inline("日", "new_menu:open_history_time:end:day"),
            ],
            [
                Button.inline("结束时", "new_menu:open_history_time:end:hour"),
                Button.inline("分", "new_menu:open_history_time:end:minute"),
                Button.inline("秒", "new_menu:open_history_time:end:second"),
            ],
            [
                Button.inline("📊 快速选择天数", "new_menu:select_days"),
                Button.inline("🗓️ 全部时间", "new_menu:set_all_time_zero"),
            ],
            [Button.inline("👈 返回上一级", "new_menu:history_task_actions")],
        ]

        timestamp = datetime.now().strftime("%H:%M:%S")
        text = (
            "📅 **历史消息时间范围选择**\n\n"
            f"{date_range_text}"
            f"当前设置: {display}\n"
            f"更新时间: {timestamp}\n\n"
            "- 第1行：起始年月日\n"
            "- 第2行：起始时分秒\n"
            "- 第3行：结束年月日\n"
            "- 第4行：结束时分秒\n"
            "- 全零配置 = 获取全部消息\n"
        )
        try:
            from utils.telegram_utils import safe_edit

            await safe_edit(event, text, buttons)
        except Exception as e:
            logger.error(f"编辑历史时间范围选择页面失败: {str(e)}")
            # 如果安全编辑失败，尝试发送新消息
            await event.respond(text, buttons=buttons)

    async def show_start_time_menu(self, event):
        session_manager.set_time_picker_context(event.chat_id, "history")
        buttons = [
            [Button.inline("📅 年份", "new_menu:select_year:history_start")],
            [Button.inline("📅 月份", "new_menu:select_month:history_start")],
            [Button.inline("📅 日期", "new_menu:select_day_of_month:history_start")],
            [Button.inline("🕐 时分", "new_menu:select_start_time")],
            [Button.inline("👈 返回上一级", "new_menu:history_time_range")],
        ]
        text = "📅 **起始点时间设置**\n\n请选择要设置的时间项目："

        try:
            from utils.telegram_utils import safe_edit

            await safe_edit(event, text, buttons)
        except Exception:
            await event.respond(text, buttons=buttons)

    async def show_end_time_menu(self, event):
        session_manager.set_time_picker_context(event.chat_id, "history")
        buttons = [
            [Button.inline("📅 年份", "new_menu:select_year:history_end")],
            [Button.inline("📅 月份", "new_menu:select_month:history_end")],
            [Button.inline("📅 日期", "new_menu:select_day_of_month:history_end")],
            [Button.inline("🕐 时分", "new_menu:select_end_time")],
            [Button.inline("👈 返回上一级", "new_menu:history_time_range")],
        ]
        text = "📅 **终止点时间设置**\n\n请选择要设置的时间项目："

        try:
            from utils.telegram_utils import safe_edit

            await safe_edit(event, text, buttons)
        except Exception:
            await event.respond(text, buttons=buttons)

    async def show_message_filter_menu(self, event):
        settings = await forward_manager.get_global_media_settings()
        # 获取当前消息数量限制配置
        message_limit = int(os.getenv("HISTORY_MESSAGE_LIMIT", "0"))
        limit_text = f"{message_limit:,}" if message_limit > 0 else "无限制"

        buttons = [
            [Button.inline("🎬 媒体类型", "new_menu:history_filter_media_types")],
            [
                Button.inline(
                    f"📝 放行文本：{'开启' if settings['allow_text'] else '关闭'}",
                    "new_menu:history_toggle_allow_text",
                )
            ],
            [Button.inline("📏 媒体时长", "new_menu:history_filter_media_duration")],
            [
                Button.inline(
                    f"📊 消息数量限制：{limit_text}", "new_menu:history_message_limit"
                )
            ],
            [Button.inline("👈 返回上一级", "new_menu:history_messages")],
        ]
        text = (
            "🔍 **历史模式 - 消息筛选**\n\n"
            "选择要修改的设置：\n\n"
            f"📊 **当前消息数量限制**：{limit_text}\n"
            "• 设置为 0 表示获取全部历史消息\n"
            "• 设置具体数值可限制获取数量，避免处理时间过长"
        )

        try:
            from utils.telegram_utils import safe_edit

            await safe_edit(event, text, buttons)
        except Exception:
            await event.respond(text, buttons=buttons)

    async def show_media_types(self, event):
        settings = await forward_manager.get_global_media_settings()
        media_types = settings["media_types"]
        buttons = [
            [
                Button.inline(
                    f"🖼️ 图片：{'开启' if media_types['image'] else '关闭'}",
                    "new_menu:history_toggle_image",
                )
            ],
            [
                Button.inline(
                    f"🎥 视频：{'开启' if media_types['video'] else '关闭'}",
                    "new_menu:history_toggle_video",
                )
            ],
            [
                Button.inline(
                    f"🎵 音乐：{'开启' if media_types['audio'] else '关闭'}",
                    "new_menu:history_toggle_music",
                )
            ],
            [
                Button.inline(
                    f"🎤 语音：{'开启' if media_types['voice'] else '关闭'}",
                    "new_menu:history_toggle_voice",
                )
            ],
            [
                Button.inline(
                    f"📄 文档：{'开启' if media_types['document'] else '关闭'}",
                    "new_menu:history_toggle_document",
                )
            ],
            [Button.inline("👈 返回上一级", "new_menu:history_message_filter")],
        ]
        text = "🎬 **历史模式 - 媒体类型**\n\n点击切换状态："

        try:
            from utils.telegram_utils import safe_edit

            await safe_edit(event, text, buttons)
        except Exception:
            await event.respond(text, buttons=buttons)

    async def show_media_duration_settings(self, event):
        buttons = await forward_manager.create_media_duration_settings_buttons()
        if (
            buttons
            and isinstance(buttons, list)
            and buttons[-1]
            and isinstance(buttons[-1], list)
        ):
            buttons[-1] = [
                Button.inline("👈 返回上一级", "new_menu:history_message_filter")
            ]
        text = "⏱️ **历史模式 - 媒体时长**\n\n配置媒体时长相关设置："

        try:
            from utils.telegram_utils import safe_edit

            await safe_edit(event, text, buttons)
        except Exception:
            await event.respond(text, buttons=buttons)

    async def show_message_limit_menu(self, event):
        """显示消息数量限制设置菜单"""
        current_limit = int(os.getenv("HISTORY_MESSAGE_LIMIT", "0"))

        # 常用的数量选项
        options = [0, 1000, 2000, 5000, 10000, 20000, 50000, 100000]
        buttons = []

        row = []
        for limit in options:
            if limit == 0:
                label = "✅ 无限制" if current_limit == 0 else "无限制"
            else:
                label = f"✅ {limit:,}" if current_limit == limit else f"{limit:,}"
            row.append(Button.inline(label, f"new_menu:set_history_limit:{limit}"))
            if len(row) == 2:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        buttons.extend(
            [
                [Button.inline("🔢 自定义数量", "new_menu:custom_history_limit")],
                [Button.inline("👈 返回上一级", "new_menu:history_message_filter")],
            ]
        )

        text = (
            "📊 **历史消息数量限制设置**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"当前限制：**{current_limit:,}** {'(无限制)' if current_limit == 0 else '条'}\n\n"
            "💡 **说明**\n"
            "• **无限制**：获取全部历史消息（推荐）\n"
            "• **有限制**：仅获取指定数量的最新消息\n"
            "• 数量越大，处理时间越长\n"
            "• 建议根据实际需要选择合适的数量\n\n"
            "📌 **选择消息数量限制**"
        )

        try:
            from utils.telegram_utils import safe_edit

            await safe_edit(event, text, buttons)
        except Exception:
            await event.respond(text, buttons=buttons)


    async def show_history_messages(self, event):
        """显示历史消息菜单"""
        buttons = [
            [Button.inline("🎯 选择处理任务", "new_menu:history_task_selection")],
            [Button.inline("🕒 时间范围选择", "new_menu:history_time_range")],
            [Button.inline("🔍 消息筛选", "new_menu:history_message_filter")],
            [Button.inline("⏱️ 转发延迟设置", "new_menu:history_delay_settings")],
            [Button.inline("📊 当前任务进度", "new_menu:current_history_task")],
            [Button.inline("🚀 开始处理历史消息", "new_menu:start_history_forward")],
            [Button.inline("👈 返回主菜单", "new_menu:main_menu")],
        ]
        await self._render_page(
            event,
            title="📂 **历史消息转发**",
            body_lines=["处理过去的消息并转发到目标频道：", "", "💡 **操作说明：**", "1. 先选择要处理的转发规则任务", "2. 设置需要转发的时间范围", "3. 按需配置消息筛选条件", "4. 点击开始处理历史消息"],
            buttons=buttons,
            breadcrumb="🏠 主菜单 > 📂 历史消息",
        )

    async def show_history_menu(self, event):
        """显示历史菜单 (show_history_messages 的别名)"""
        await self.show_history_messages(event)

    async def show_history_task_selector(self, event):
        """显示历史任务选择器"""
        try:
            from ..forward_management import forward_manager
            rules = await forward_manager.get_channel_rules()
            current_rule_id = await session_manager.get_selected_rule(event.chat_id)

            buttons = []
            for rule in rules[:20]:
                is_curr = current_rule_id == rule.id
                s_name = rule.source_chat.name if rule.source_chat else "未知"
                t_name = rule.target_chat.name if rule.target_chat else "未知"
                buttons.append([Button.inline(f"{'✅' if is_curr else '☐'} 规则{rule.id}: {s_name} → {t_name}", f"new_menu:select_task:{rule.id}")])

            buttons.append([Button.inline("👈 返回上一级", "new_menu:history_messages")])
            await self._render_from_text(event, "🎯 **选择历史任务**\n\n请选择要处理的转发规则：", buttons)
        except Exception as e:
            logger.error(f"显示历史任务选择器失败: {e}")

    async def show_current_history_task(self, event):
        """显示当前历史任务"""
        try:
            prog = await session_manager.get_history_progress(event.chat_id)
            done, total = prog.get("done", 0), prog.get("total", 0)
            status = prog.get("status", "idle")
            percent = (done * 100 // total) if total else 0
            bar = "█" * (percent // 5) + "░" * (20 - percent // 5)
            
            text = (
                "📊 **当前任务进度**\n\n"
                f"状态: {status}\n"
                f"进度: {done}/{total} ({percent}%)\n"
                f"[{bar}]\n\n"
                "💡 任务在后台运行中，可随时刷新查看进度。"
            )
            buttons = [[Button.inline("🔄 刷新", "new_menu:current_history_task")], [Button.inline("👈 返回上一级", "new_menu:history_messages")]]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"显示当前历史任务失败: {e}")

    async def show_history_delay_settings(self, event):
        """显示历史延迟设置"""
        try:
            delay = await session_manager.get_history_delay(event.chat_id)
            options = [0, 1, 2, 3, 5, 10, 15, 30]
            buttons = []
            row = []
            for v in options:
                row.append(Button.inline(f"{v}s{' ✅' if v == delay else ''}", f"new_menu:set_history_delay:{v}"))
                if len(row) == 4: buttons.append(row); row = []
            if row: buttons.append(row)
            buttons.append([Button.inline("👈 返回上一级", "new_menu:history_messages")])
            await self._render_from_text(event, f"⏱️ **转发延迟设置**\n\n当前延迟: {delay}s\n\n请选择延迟：", buttons)
        except Exception as e:
            logger.error(f"显示历史延迟设置失败: {e}")

history_module = HistoryModule()
