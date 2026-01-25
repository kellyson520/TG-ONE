"""
筛选设置菜单模块
处理媒体类型、大小、时长、扩展名等全局或规则特定的筛选逻辑
"""
import logging
from telethon import Button
from ..base import BaseMenu
from ..forward_management import forward_manager

logger = logging.getLogger(__name__)

class FilterMenu(BaseMenu):
    """筛选设置菜单"""

    async def show_filter_settings(self, event):
        """显示筛选设置菜单"""
        buttons = [
            [Button.inline("🎬 媒体类型", "new_menu:filter_media_types")],
            [Button.inline("📏 媒体大小", "new_menu:filter_media_size")],
            [Button.inline("⏱️ 媒体时长", "new_menu:filter_media_duration")],
            [Button.inline("📁 媒体扩展", "new_menu:filter_media_extension")],
            [Button.inline("👈 返回上一级", "new_menu:forward_management")],
        ]
        await self._render_page(
            event,
            title="🔍 **全自动媒体筛选**",
            body_lines=["配置全局媒体转发筛选规则："],
            buttons=buttons,
            breadcrumb="🏠 主菜单 > 🔄 转发管理 > 🔍 筛选设置",
        )

    async def show_media_types(self, event):
        """显示媒体类型菜单"""
        settings = await forward_manager.get_global_media_settings()
        media_types = settings["media_types"]
        
        buttons = [
            [Button.inline(f"🖼️ 图片：{'开启' if media_types['image'] else '关闭'}", "new_menu:toggle_media_type:image")],
            [Button.inline(f"🎥 视频：{'开启' if media_types['video'] else '关闭'}", "new_menu:toggle_media_type:video")],
            [Button.inline(f"🎵 音乐：{'开启' if media_types['audio'] else '关闭'}", "new_menu:toggle_media_type:audio")],
            [Button.inline(f"🎤 语音：{'开启' if media_types['voice'] else '关闭'}", "new_menu:toggle_media_type:voice")],
            [Button.inline(f"📄 文档：{'开启' if media_types['document'] else '关闭'}", "new_menu:toggle_media_type:document")],
            [Button.inline(f"📝 文本：{'开启' if settings.get('allow_text',True) else '关闭'}", "new_menu:toggle_allow_text")],
            [Button.inline("👈 返回上一级", "new_menu:filter_settings")],
        ]
        await self._render_from_text(event, "🎬 **媒体类型筛选**\n\n点击切换状态：", buttons)

    async def show_media_size_settings(self, event):
        """显示媒体大小设置"""
        buttons = await forward_manager.create_media_size_settings_buttons()
        await self._render_from_text(event, "📏 **媒体大小过滤**\n\n配置媒体文件的大小限制：", buttons)

    async def show_media_duration_settings(self, event):
        """显示媒体时长设置"""
        buttons = await forward_manager.create_media_duration_settings_buttons()
        await self._render_from_text(event, "⏱️ **媒体时长过滤**\n\n配置媒体文件的播放时长限制：", buttons)

    async def show_media_extension_settings(self, event):
        """显示媒体扩展设置"""
        buttons = await forward_manager.create_media_extension_settings_buttons()
        await self._render_from_text(event, "📁 **媒体扩展过滤**\n\n配置允许或屏蔽的媒体文件扩展名：", buttons)

filter_menu = FilterMenu()
