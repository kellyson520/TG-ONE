"""
转发管理功能模块
"""


import logging
from telethon import Button

from services.forward_settings_service import forward_settings_service

logger = logging.getLogger(__name__)


class ForwardManager:
    """转发管理器"""

    def __init__(self):
        self._global_settings = None # Deprecated, kept for compat if needed, but service handles cache

    async def get_global_media_settings(self):
        """获取全局媒体设置"""
        return await forward_settings_service.get_global_media_settings()

    async def update_global_media_setting(self, key, value):
        """更新全局媒体设置"""
        return await forward_settings_service.update_global_media_setting(key, value)

    async def set_media_size_limit(self, limit_mb: int):
        """设置媒体大小限制（MB）"""
        return await forward_settings_service.set_media_size_limit(limit_mb)

    async def get_media_extensions_options(self):
        """获取可选的媒体扩展名列表（优先从配置加载）"""
        return await forward_settings_service.get_media_extensions_options()

    async def toggle_media_extension(self, extension: str):
        """切换某个媒体扩展名是否启用"""
        return await forward_settings_service.toggle_media_extension(extension)

    async def toggle_media_type(self, media_type):
        """切换媒体类型状态"""
        return await forward_settings_service.toggle_media_type(media_type)

    async def toggle_extension_filter_mode(self):
        """切换扩展名过滤模式"""
        res = await forward_settings_service.toggle_extension_mode()
        return res.get('new_mode', 'blacklist')

    async def get_channel_rules(self):
        """获取频道规则列表"""
        try:
            from services.rule_service import RuleQueryService

            logger.info("正在从数据库查询转发规则...")
            rules = await RuleQueryService.get_all_rules_with_chats()
            logger.info(f"从数据库获取到 {len(rules)} 个转发规则")
            return rules
        except Exception as e:
            logger.error(f"获取频道规则失败: {str(e)}", exc_info=True)
            return []

    async def get_rule_status_text(self, rule):
        """获取规则状态文本"""
        try:
            status = "启用" if rule.enable_rule else "禁用"
            source_name = rule.source_chat.name if rule.source_chat else "未知源"
            target_name = rule.target_chat.name if rule.target_chat else "未知目标"
            return f"{source_name}→{target_name}（{status}）"
        except Exception as e:
            logger.error(f"获取规则 {rule.id} 状态文本失败: {str(e)}")
            # 返回简单的状态文本作为后备
            status = "启用" if getattr(rule, "enable_rule", True) else "禁用"
            return f"规则{rule.id}（{status}）"

    async def toggle_rule_status(self, rule_id):
        """切换规则启用状态"""
        from core.container import container
        from models.models import ForwardRule
        async with container.db.get_session() as session:
            try:
                # 获取规则
                rule = await session.get(ForwardRule, rule_id)
                if rule:
                    rule.enable_rule = not rule.enable_rule
                    await session.commit()
                    # 失效缓存（源/目标聊天）
                    try:
                        from services.rule_service import RuleQueryService

                        if rule.source_chat_id:
                            RuleQueryService.invalidate_caches_for_chat(
                                rule.source_chat_id
                            )
                        if rule.target_chat_id:
                            RuleQueryService.invalidate_caches_for_chat(
                                rule.target_chat_id
                            )
                    except Exception as e:
                        logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
                    return True, rule.enable_rule
                return False, None
            except Exception as e:
                await session.rollback()
                logger.error(f"切换规则状态失败: {str(e)}")
                return False, None

    async def create_media_size_settings_buttons(self):
        """创建媒体大小设置按钮"""
        settings = await self.get_global_media_settings()
        size_filter_enabled = settings.get("media_size_filter_enabled", False)
        size_alert_enabled = settings.get("media_size_alert_enabled", False)
        size_limit_mb = settings.get("media_size_limit", 100)

        buttons = [
            [
                Button.inline(
                    f"📏 媒体大小过滤：{'开启' if size_filter_enabled else '关闭'}",
                    "new_menu:toggle_media_size_filter",
                )
            ],
            [
                Button.inline(
                    f"📐 媒体大小限制：{size_limit_mb}MB",
                    "new_menu:set_media_size_limit",
                )
            ],
            [
                Button.inline(
                    f"⚠️ 媒体大小超限发提示：{'开启' if size_alert_enabled else '关闭'}",
                    "new_menu:toggle_media_size_alert",
                )
            ],
            [Button.inline("👈 返回上一级", "new_menu:filter_settings")],
        ]
        return buttons

    async def create_media_duration_settings_buttons(self):
        """创建媒体时长设置按钮"""
        settings = await self.get_global_media_settings()
        duration_enabled = settings.get("media_duration_enabled", False)
        min_sec = int(settings.get("duration_min_seconds", 0) or 0)
        max_sec = int(settings.get("duration_max_seconds", 0) or 0)
        range_text = self._format_duration_range(min_sec, max_sec)

        # 计算起始时长的各单位分量
        def seconds_to_components(total: int):
            if total < 0:
                total = 0
            days = total // 86400
            hours = (total % 86400) // 3600
            minutes = (total % 3600) // 60
            seconds = total % 60
            return days, hours, minutes, seconds

        min_days, min_hours, min_minutes, min_seconds = seconds_to_components(min_sec)
        max_days, max_hours, max_minutes, max_seconds = seconds_to_components(max_sec)

        # 顶部四段（等宽）- 显示单位+占位数字（未设置或为0时显示 --）
        def placeholder(val: int) -> str:
            return f"{val}" if (duration_enabled and val > 0) else "--"

        # 起始（最小）行
        top_row = [
            Button.inline(
                f"天 {placeholder(min_days)}", "new_menu:open_duration_picker:min:days"
            ),
            Button.inline(
                f"时 {placeholder(min_hours)}",
                "new_menu:open_duration_picker:min:hours",
            ),
            Button.inline(
                f"分 {placeholder(min_minutes)}",
                "new_menu:open_duration_picker:min:minutes",
            ),
            Button.inline(
                f"秒 {placeholder(min_seconds)}",
                "new_menu:open_duration_picker:min:seconds",
            ),
        ]

        # 结束（最大）行（0 表示无限大）
        def placeholder_max(val: int) -> str:
            # 当最大为 0 时，各分量显示 --
            return (
                "--"
                if (not duration_enabled or max_sec == 0)
                else (f"{val}" if val > 0 else "--")
            )

        bottom_row = [
            Button.inline(
                f"天 {placeholder_max(max_days)}",
                "new_menu:open_duration_picker:max:days",
            ),
            Button.inline(
                f"时 {placeholder_max(max_hours)}",
                "new_menu:open_duration_picker:max:hours",
            ),
            Button.inline(
                f"分 {placeholder_max(max_minutes)}",
                "new_menu:open_duration_picker:max:minutes",
            ),
            Button.inline(
                f"秒 {placeholder_max(max_seconds)}",
                "new_menu:open_duration_picker:max:seconds",
            ),
        ]

        buttons = [
            [
                Button.inline(
                    f"⏱️ 媒体时长：{'开启' if duration_enabled else '关闭'}",
                    "new_menu:toggle_media_duration",
                )
            ],
            top_row,
            bottom_row,
            [
                Button.inline(
                    f"⏰ 当前区间：{range_text}", "new_menu:set_duration_range"
                )
            ],
            [Button.inline("👈 返回上一级", "new_menu:filter_settings")],
        ]
        return buttons

    def _format_duration(self, seconds: int) -> str:
        if seconds <= 0:
            return "0s"
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        parts = []
        if d:
            parts.append(f"{d}d")
        if h:
            parts.append(f"{h}h")
        if m:
            parts.append(f"{m}m")
        if s:
            parts.append(f"{s}s")
        return " ".join(parts) if parts else "0s"

    def _format_duration_range(self, min_sec: int, max_sec: int) -> str:
        min_text = self._format_duration(min_sec)
        max_text = "∞" if max_sec <= 0 else self._format_duration(max_sec)
        return f"{min_text} - {max_text}"

    async def get_duration_settings(self):
        settings = await self.get_global_media_settings()
        return {
            "enabled": bool(settings.get("media_duration_enabled", False)),
            "min_seconds": int(settings.get("duration_min_seconds", 0) or 0),
            "max_seconds": int(settings.get("duration_max_seconds", 0) or 0),
        }

    async def set_duration_component(self, side: str, unit: str, value: int):
        """设置时长区间的某个分量，side=min|max, unit=days|hours|minutes|seconds"""
        settings = await self.get_global_media_settings()
        min_seconds = int(settings.get("duration_min_seconds", 0) or 0)
        max_seconds = int(settings.get("duration_max_seconds", 0) or 0)

        def seconds_to_components(total: int):
            if total < 0:
                total = 0
            days = total // 86400
            hours = (total % 86400) // 3600
            minutes = (total % 3600) // 60
            seconds = total % 60
            return days, hours, minutes, seconds

        def components_to_seconds(days: int, hours: int, minutes: int, seconds: int):
            return max(
                0,
                int(days) * 86400
                + int(hours) * 3600
                + int(minutes) * 60
                + int(seconds),
            )

        min_d, min_h, min_m, min_s = seconds_to_components(min_seconds)
        max_d, max_h, max_m, max_s = seconds_to_components(max_seconds)

        if side == "min":
            if unit == "days":
                min_d = value
            elif unit == "hours":
                min_h = value
            elif unit == "minutes":
                min_m = value
            elif unit == "seconds":
                min_s = value
            min_seconds = components_to_seconds(min_d, min_h, min_m, min_s)
        else:
            if unit == "days":
                max_d = value
            elif unit == "hours":
                max_h = value
            elif unit == "minutes":
                max_m = value
            elif unit == "seconds":
                max_s = value
            max_seconds = components_to_seconds(max_d, max_h, max_m, max_s)

        # 不强制关系，但可选保障 max>=min（若开启过滤）
        try:
            await forward_settings_service.update_global_media_setting("duration_min_seconds", min_seconds)
            await forward_settings_service.update_global_media_setting("duration_max_seconds", max_seconds)
            return True
        except Exception as e:
            logger.error(f"保存时长区间失败: {str(e)}")
            return False

    async def create_media_extension_settings_buttons(self):
        """创建媒体扩展设置按钮"""
        settings = await self.get_global_media_settings()
        selected = set(settings.get("media_extensions", []))
        options = await self.get_media_extensions_options()

        buttons = [
            [
                Button.inline(
                    "📁 过滤模式（黑/白名单）", "new_menu:toggle_extension_mode"
                )
            ]
        ]

        # 生成扩展名按钮（每行最多放置4个）
        row = []
        for ext in options:
            is_selected = ext in selected
            text = f"{'✅ ' if is_selected else ''}{ext}"
            row.append(Button.inline(text, f"new_menu:toggle_ext:{ext}"))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([Button.inline("👈 返回上一级", "new_menu:filter_settings")])
        return buttons


# 创建全局转发管理器实例
forward_manager = ForwardManager()
