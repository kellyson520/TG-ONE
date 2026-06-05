"""
会话管理菜单模块
处理消息去重扫描、批量删除消息等
"""
import logging
from telethon import Button
from ..base import BaseMenu
from services.session_service import session_manager

logger = logging.getLogger(__name__)

class SessionMenu(BaseMenu):
    """会话管理菜单"""

    async def show_session_management(self, event):
        """显示会话管理菜单"""
        buttons = [
            [Button.inline("🔍 会话消息去重", "new_menu:session_dedup")],
            [Button.inline("🗑️ 删除会话消息", "new_menu:delete_session_messages")],
            [Button.inline("👈 返回上一级", "new_menu:system_hub")],
        ]
        await self._render_page(
            event,
            title="💬 **会话管理**",
            body_lines=["选择会话管理功能："],
            buttons=buttons,
            breadcrumb="🏠 主菜单 > 📋 会话管理",
        )

    async def show_session_dedup_menu(self, event):
        """显示会话消息去重菜单"""
        buttons = [
            [Button.inline("🚀 开始扫描", "new_menu:start_dedup_scan")],
            [Button.inline("📊 扫描结果", "new_menu:dedup_results")],
            [Button.inline("📅 会话时间范围选择", "new_menu:session_dedup_time_range")],
            [Button.inline("⚙️ 去重详细设置", "new_menu:dedup_config")],
            [Button.inline("👈 返回上一级", "new_menu:session_management")],
        ]
        await self._render_page(
            event,
            title="🔍 **会话消息去重**",
            body_lines=[
                "系统将使用官方API优化扫描当前会话中的重复消息。", "",
                "**✨ 优化特性：**",
                "• 使用Telegram官方搜索API", "• 分类并发扫描不同媒体类型",
                "• 支持全消息扫描（无数量限制）", "• 智能回退机制确保兼容性",
                "", "请选择操作：",
            ],
            buttons=buttons,
            breadcrumb="🏠 主菜单 > 📋 会话管理 > 🧹 会话去重",
        )

    async def show_dedup_results(self, event):
        """显示去重扫描结果"""
        try:
            chat_id = event.chat_id
            scan_results_cache = session_manager._get_cached_scan_result(chat_id)
            if scan_results_cache is not None:
                if scan_results_cache:
                    scan_results = {session_manager._signature_to_display_name(sig): len(ids) for sig, ids in scan_results_cache.items()}
                else: scan_results = {}
            else:
                text = "📊 **扫描报告**\n\n⚠️ 尚未进行扫描\n\n请先运行扫描以获取重复消息分析结果。"
                buttons = [[Button.inline("🚀 开始扫描", "new_menu:start_dedup_scan")], [Button.inline("👈 返回上一级", "new_menu:session_dedup")]]
                await self._render_from_text(event, text, buttons)
                return

            if not scan_results:
                text = "📊 **扫描报告**\n\n✨ 未发现重复文件\n\n当前会话中的所有消息都是唯一的。"
                buttons = [[Button.inline("🔄 重新扫描", "new_menu:start_dedup_scan_optimized")],[Button.inline("👈 返回上一级", "new_menu:session_dedup")]]
            else:
                total_duplicates = sum(scan_results.values())
                result_text = "\n".join([f"📄 {filename} ×{count}" for filename, count in scan_results.items()])
                text = (
                    "📊 **扫描报告**\n\n"
                    f"🎯 发现 **{len(scan_results)}** 种重复内容\n"
                    f"📈 总计 **{total_duplicates}** 条重复消息\n\n"
                    f"**详细列表：**\n{result_text}\n"
                    "请选择处理方式："
                )
                buttons = [
                    [Button.inline("🗑️ 全部删除", "new_menu:delete_all_duplicates")],
                    [Button.inline("✅ 全部保留", "new_menu:keep_all_duplicates")],
                    [Button.inline("🔧 选择删除", "new_menu:select_delete_duplicates")],
                    [Button.inline("🔄 重新扫描", "new_menu:start_dedup_scan_optimized")],
                    [Button.inline("👈 返回上一级", "new_menu:session_dedup")],
                ]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"显示去重结果失败: {str(e)}")
            await self._render_from_text(event, "❌ **获取扫描结果失败**", [[Button.inline("🔄 重新扫描", "new_menu:start_dedup_scan")], [Button.inline("👈 返回上一级", "new_menu:session_dedup")]])

    async def start_dedup_scan(self, event):
        """启动去重扫描"""
        try:
            start_text = (
                "🚀 **智能扫描启动中...**\n\n"
                "正在使用官方API分类扫描：\n"
                "🖼️ 图片文件 / 🎥 视频文件 / 📄 文档文件 / 🎵 音乐文件 / 🎙️ 语音文件 / 📝 文本消息\n\n"
                "⏳ 请稍候，这可能需要几分钟...\n💡 如API不可用会自动回退到传统扫描"
            )
            buttons = [[Button.inline("❌ 取消", "new_menu:session_dedup")]]
            await self._render_from_text(event, start_text, buttons)

            last_update = [0]
            async def progress_callback(processed, signatures_found):
                from datetime import datetime
                curr = datetime.now().timestamp()
                if processed - last_update[0] >= 5000 or curr - last_update[0] >= 30:
                    try:
                        await event.edit(f"🚀 **智能扫描进行中...**\n\n📊 已处理: **{processed:,}** 条\n🔍 已发现: **{signatures_found:,}** 签名", buttons=buttons)
                        last_update[0] = processed
                    except Exception as e:
                        logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

            results = await session_manager.scan_duplicate_messages(event, progress_callback=progress_callback)
            if results:
                total = sum(len(ids) for ids in results.values())
                await self._render_from_text(event, f"✅ **扫描完成！**\n\n🎯 发现 **{len(results)}** 种重复内容\n📈 总计 **{total}** 条重复消息", [
                    [Button.inline("📊 查看详细结果", "new_menu:dedup_results")],
                    [Button.inline("🗑️ 全部删除", "new_menu:delete_all_duplicates")],
                    [Button.inline("🔧 选择删除", "new_menu:select_delete_duplicates")],
                    [Button.inline("👈 返回菜单", "new_menu:session_dedup")]
                ])
            else:
                await self._render_from_text(event, "✨ **扫描完成**\n\n🎉 未发现重复消息！", [[Button.inline("👈 返回菜单", "new_menu:session_dedup")]])
        except Exception as e:
            logger.error(f"扫描失败: {str(e)}")
            await self._render_from_text(event, f"❌ **扫描失败**\n\n{e}", [[Button.inline("🔄 重新扫描", "new_menu:start_dedup_scan")], [Button.inline("👈 返回菜单", "new_menu:session_dedup")]])

    async def show_select_delete_menu(self, event):
        """显示选择删除菜单"""
        try:
            scan_counts = await session_manager.scan_duplicate_messages(event)
            if not scan_counts:
                await self._render_from_text(event, "❌ 没有找到重复项可供选择", [[Button.inline("👈 返回上一级", "new_menu:dedup_results")]])
            else:
                buttons = []
                selected = await session_manager.get_selection_state(event.chat_id)
                for sig, ids in scan_counts.items():
                    import hashlib
                    short_id = hashlib.md5(sig.encode()).hexdigest()[:8]
                    is_sel = sig in selected
                    display_name = session_manager._signature_to_display_name(sig)
                    buttons.append([Button.inline(f"{'✅' if is_sel else '☐'} {display_name} ×{len(ids)}", f"new_menu:toggle_select:{short_id}")])
                buttons.extend([[Button.inline("🗑️ 删除选中项", "new_menu:delete_selected_duplicates")], [Button.inline("👈 返回上一级", "new_menu:dedup_results")]])
                await self._render_from_text(event, "🔧 **选择删除**\n\n请选择要删除的重复项：", buttons)
        except Exception as e:
            logger.error(f"显示选择删除菜单失败: {str(e)}")
            await self._render_from_text(event, "❌ 获取重复项列表失败", [[Button.inline("👈 返回上一级", "new_menu:dedup_results")]])


    async def confirm_delete_all_duplicates(self, event):
        """确认删除所有重复项"""
        buttons = [
            [Button.inline("✅ 确认删除", "new_menu:execute_delete_all")],
            [Button.inline("❌ 取消", "new_menu:dedup_results")],
        ]
        await self._render_from_text(event, "❓ **危险操作确认**\n\n确定要删除所有发现的重复消息吗？\n此操作不可撤销！", buttons)

    async def execute_delete_all_duplicates(self, event):
        """执行删除所有重复项"""
        try:
            success, message = await session_manager.delete_duplicate_messages(event, mode="all")
            if success:
                await event.answer("✅ 删除任务已后台启动")
                await self.show_session_dedup_menu(event)
            else:
                await event.answer(f"❌ 启动失败: {message}", alert=True)
        except Exception as e:
            logger.error(f"执行删除失败: {e}")
            await event.answer("操作异常", alert=True)

    async def show_delete_session_messages_menu(self, event):
        """显示批量删除会话消息菜单"""
        try:
            time_str = await session_manager.get_time_range_display(event.chat_id)
        except Exception as e:
            time_str = "未设置"
        
        buttons = [
            [Button.inline("📅 设置时间范围", "new_menu:time_range_selection")],
            [Button.inline("🔍 消息筛选条件", "new_menu:message_filter")],
            [Button.inline("👁️ 预览将删除消息", "new_menu:preview_delete")],
            [Button.inline("🗑️ 开始批量删除", "new_menu:confirm_delete")],
            [Button.inline("⏸️ 暂停任务", "new_menu:pause_delete"), Button.inline("⏹️ 停止任务", "new_menu:stop_delete")],
            [Button.inline("👈 返回上一级", "new_menu:session_management")],
        ]
        
        # 获取进度
        try:
            prog = await session_manager.get_delete_progress(event.chat_id)
            deleted = prog.get("deleted", 0)
            total = prog.get("total", 0)
            status_text = f"已删除: {deleted}"
        except Exception as e:
            status_text = "就绪"

        await self._render_page(
            event,
            title="🗑️ **批量删除消息**",
            body_lines=[
                f"当前时间范围: {time_str}",
                f"任务状态: {status_text}",
                "",
                "⚠️ 请先设置时间范围并预览，确认无误后再执行删除。",
            ],
            buttons=buttons,
            breadcrumb="🏠 主菜单 > 📋 会话管理 > 🗑️ 批量删除",
        )

    async def show_preview_delete(self, event):
        """显示删除预览"""
        try:
            count, samples = await session_manager.preview_session_messages_by_filter(event)
            sample_text = "\n".join([f"• [{m.id}] {m.text[:20]}..." for m in samples]) if samples else "无"
            text = (
                f"👁️ **删除预览**\n\n"
                f"预计匹配消息数: **{count}**\n\n"
                f"**示例消息:**\n{sample_text}\n"
            )
            buttons = [
                [Button.inline("🔄 刷新预览", "new_menu:preview_delete_refresh")],
                [Button.inline("👈 返回上一级", "new_menu:delete_session_messages")],
            ]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"预览失败: {e}")
            await event.answer("预览失败", alert=True)

    async def show_message_filter_menu(self, event):
        """显示消息筛选菜单"""
        # 复用 FilterMenu 的逻辑，或者简单的跳转
        from .filter_menu import filter_menu
        await filter_menu.show_filter_settings(event)

    async def show_dedup_config(self, event):
        """显示去重配置菜单"""
        from ..forward_management import forward_manager
        settings = await forward_manager.get_global_media_settings()
        enabled = settings.get("dedup_enabled", True)
        mode = settings.get("dedup_mode", "hash")
        
        buttons = [
            [Button.inline(f"🔄 去重总开关：{'开启' if enabled else '关闭'}", "new_menu:toggle_dedup_enabled")],
            [Button.inline(f"📊 策略：{'内容哈希' if mode == 'hash' else '签名匹配'}", "new_menu:toggle_dedup_mode")],
            [Button.inline("👈 返回上一级", "new_menu:session_dedup")],
        ]
        
        text = (
            "⚙️ **去重详细设置**\n\n"
            f"当前状态：{'✅ 已开启' if enabled else '❌ 已关闭'}\n"
            f"当前策略：{'📋 内容哈希 (精准)' if mode == 'hash' else '🖼️ 签名匹配 (快速)'}\n\n"
            "💡 **说明**\n"
            "• **内容哈希**：通过消息特征计算摘要，能识别不同文件但内容相同的消息。\n"
            "• **签名匹配**：基于文件名、大小、分辨率等元数据匹配，速度快但可能误杀或漏杀。"
        )
        await self._render_from_text(event, text, buttons)

session_menu = SessionMenu()
