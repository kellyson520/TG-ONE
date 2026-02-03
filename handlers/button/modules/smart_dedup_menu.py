"""
智能去重设置菜单模块
处理全局去重策略、相似度阈值、内容哈希等配置
"""
import logging
from telethon import Button
from ..base import BaseMenu
from services.dedup.engine import smart_deduplicator

logger = logging.getLogger(__name__)

class SmartDedupMenu(BaseMenu):
    """智能去重设置菜单"""

    async def show_smart_dedup_settings(self, event):
        """显示智能去重设置主界面"""
        try:
            config = smart_deduplicator.config
            stats = smart_deduplicator.get_stats()
            text = "🧹 **智能去重设置**\n\n"
            text += "⚙️ **当前配置**\n"
            text += f"时间窗口去重: {'✅' if config.get('enable_time_window') else '❌'}\n"
            hours = int(config.get("time_window_hours", 24) or 24)
            text += f"时间窗口: {'永久' if hours <= 0 else str(hours)+' 小时'}\n"
            text += f"内容哈希去重: {'✅' if config.get('enable_content_hash') else '❌'}\n"
            text += f"智能相似度: {'✅' if config.get('enable_smart_similarity') else '❌'}\n"
            text += f"相似度阈值: {config.get('similarity_threshold', 0.85):.0%}\n\n"
            text += f"📊 **运行状态**\n缓存签名: {stats.get('cached_signatures', 0)}\n缓存哈希: {stats.get('cached_content_hashes', 0)}\n\n"
            
            buttons = [
                [Button.inline("⏰ 时间窗口设置", "new_menu:dedup_time_window"), Button.inline("🔍 相似度设置", "new_menu:dedup_similarity")],
                [Button.inline("📋 内容哈希设置", "new_menu:dedup_content_hash"), Button.inline("🎞️ 视频去重", "new_menu:dedup_video")],
                [Button.inline("🎛️ 高级设置", "new_menu:dedup_advanced"), Button.inline("📊 去重统计", "new_menu:dedup_statistics")],
                [Button.inline("🗑️ 清理缓存", "new_menu:dedup_clear_cache"), Button.inline("🔄 刷新状态", "new_menu:smart_dedup_settings")],
                [Button.inline("👈 返回主菜单", "new_menu:main_menu")],
            ]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"显示智能去重设置失败: {e}")
            await event.answer("加载去重设置失败", alert=True)

    async def show_dedup_similarity(self, event):
        """相似度检测设置"""
        try:
            config = smart_deduplicator.config
            enabled = config.get("enable_smart_similarity", True)
            threshold = config.get("similarity_threshold", 0.85)
            text = f"🔍 **智能相似度检测设置**\n\n当前状态: {'✅ 启用' if enabled else '❌ 禁用'}\n相似度阈值: {threshold:.0%}\n\n💡 建议开启以获得最佳去重效果。"
            buttons = [
                [Button.inline(f"{'🔴 关闭' if enabled else '🟢 开启'}", f"new_menu:toggle_similarity:{not enabled}")],
                [Button.inline("70%", "new_menu:set_similarity:0.7"), Button.inline("85%⭐", "new_menu:set_similarity:0.85"), Button.inline("95%", "new_menu:set_similarity:0.95")],
                [Button.inline("👈 返回去重设置", "new_menu:smart_dedup_settings")],
            ]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"显示相似度设置失败: {e}")
            await event.answer("加载失败", alert=True)

    async def show_dedup_content_hash(self, event):
        """内容哈希去重设置"""
        try:
            enabled = smart_deduplicator.config.get("enable_content_hash", True)
            text = f"📋 **内容哈希去重设置**\n\n当前状态: {'✅ 启用' if enabled else '❌ 禁用'}\n\n内容哈希基于消息特征，能够精准识别跨文件的相同内容。"
            buttons = [
                [Button.inline(f"{'🔴 关闭' if enabled else '🟢 开启'}", f"new_menu:toggle_content_hash:{not enabled}")],
                [Button.inline("👈 返回去重设置", "new_menu:smart_dedup_settings")],
            ]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"内容哈希设置失败: {e}")

    async def show_dedup_video(self, event):
        """视频去重设置"""
        try:
            config = smart_deduplicator.config
            e_id = config.get("enable_video_file_id_check", True)
            e_hash = config.get("enable_video_partial_hash_check", True)
            text = f"🎞️ **视频去重设置**\n\nfile_id 判重: {'✅' if e_id else '❌'}\n部分内容哈希: {'✅' if e_hash else '❌'}\n\n建议保持双开。"
            buttons = [
                [Button.inline(f"{'🔴 关闭' if e_id else '🟢 开启'} file_id", f"new_menu:toggle_video_file_id:{not e_id}")],
                [Button.inline(f"{'🔴 关闭' if e_hash else '🟢 开启'} 部分哈希", f"new_menu:toggle_video_partial:{not e_hash}")],
                [Button.inline("👈 返回去重设置", "new_menu:smart_dedup_settings")],
            ]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"视频去重失败: {e}")

    async def show_dedup_statistics(self, event):
        """去重统计"""
        try:
            stats = smart_deduplicator.get_stats()
            text = "📊 **智能去重统计**\n\n"
            text += f"签名缓存: {stats.get('cached_signatures', 0)}\n"
            text += f"哈希缓存: {stats.get('cached_content_hashes', 0)}\n"
            text += f"跟踪聊天: {stats.get('tracked_chats', 0)}\n"
            text += f"今日活跃会话: {stats.get('active_chats_today', 0)}\n"
            
            buttons = [
                [Button.inline("🔄 刷新", "new_menu:dedup_statistics")],
                [Button.inline("👈 返回去重设置", "new_menu:smart_dedup_settings")]
            ]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"统计失败: {e}")
            await event.answer("加载统计失败", alert=True)

    async def show_dedup_time_window(self, event):
        """时间窗口去重设置"""
        try:
            config = smart_deduplicator.config
            enabled = config.get("enable_time_window", True)
            hours = int(config.get("time_window_hours", 24) or 24)
            
            text = "⏰ **时间窗口去重设置**\n\n"
            text += f"当前状态: {'✅ 启用' if enabled else '❌ 禁用'}\n"
            text += f"当前窗口: {hours} 小时\n\n"
            text += "💡 窗口内出现过的相同签名将被拦截。"
            
            buttons = [
                [Button.inline(f"{'🔴 关闭' if enabled else '🟢 开启'}", f"new_menu:toggle_time_window:{not enabled}")],
                [Button.inline("1小时", "new_menu:set_time_window:1"), Button.inline("6小时", "new_menu:set_time_window:6"), Button.inline("12小时", "new_menu:set_time_window:12")],
                [Button.inline("24小时", "new_menu:set_time_window:24"), Button.inline("48小时", "new_menu:set_time_window:48"), Button.inline("72小时", "new_menu:set_time_window:72")],
                [Button.inline("👈 返回去重设置", "new_menu:smart_dedup_settings")],
            ]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"时间窗口设置失败: {e}")
            await event.answer("加载失败", alert=True)

    async def show_dedup_advanced(self, event):
        """高级去重设置"""
        try:
            config = smart_deduplicator.config
            text = "🎛️ **高级去重设置**\n\n"
            text += f"持久化缓存: {'✅' if config.get('enable_persistent_cache') else '❌'}\n"
            text += f"清理间隔: {config.get('cache_cleanup_interval', 3600)}s\n"
            text += f"SimHash 指纹: {'✅' if config.get('enable_text_fingerprint') else '❌'}\n"
            
            buttons = [
                [Button.inline("哈希特征示例", "new_menu:dedup_hash_examples")],
                [Button.inline("手动触发清理", "new_menu:manual_cleanup")],
                [Button.inline("重置默认配置", "new_menu:reset_dedup_config")],
                [Button.inline("👈 返回去重设置", "new_menu:smart_dedup_settings")],
            ]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"高级设置加载失败: {e}")
            await event.answer("加载失败", alert=True)

    async def show_dedup_hash_examples(self, event):
        """显示哈希特征示例"""
        text = "📋 **哈希特征示例**\n\n"
        text += "去重系统会提取消息的以下特征：\n"
        text += "1. **文本**: 移除链接、提及、表情后的核心内容\n"
        text += "2. **视频**: 基于 file_id 或首尾固定分块的 MD5\n"
        text += "3. **图片**: 基于分辨率和文件大小的复合签名\n"
        
        buttons = [[Button.inline("👈 返回高级设置", "new_menu:dedup_advanced")]]
        await self._render_from_text(event, text, buttons)

smart_dedup_menu = SmartDedupMenu()
