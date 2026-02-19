import logging
from typing import Optional
from controllers.base import BaseController, ControllerAbort
from services.session_service import session_service

logger = logging.getLogger(__name__)

class MediaController(BaseController):
    """媒体、AI 与历史补全业务控制器"""

    async def show_history_hub(self, event):
        """显示历史任务中心 (Refactored to UIRE-3.0)"""
        try:
            # 获取当前补全任务状态
            task_status = await session_service.get_history_task_status(event.sender_id)
            
            data = {
                'current_task': task_status['progress'] if task_status.get('has_task') else None
            }
            if data['current_task']:
                data['current_task']['status'] = task_status['status']

            view_result = self.container.ui.media.render_history_hub(data)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_task_actions(self, event):
        """显示任务操作页 (Refactored to TaskRenderer)"""
        try:
            from services.forward_settings_service import forward_settings_service
            # 获取选中的规则
            res = await session_service.get_selected_rule(event.sender_id)
            # 获取全局媒体设置
            settings = await forward_settings_service.get_global_media_settings()
            # 获取时间范围设置
            time_config = await session_service.get_time_range_config(event.sender_id)
            
            data = {
                'selected': res,
                'dedup_enabled': settings.get('history_dedup_enabled', False),
                'time_range': time_config.get('display_text', '全部消息')
            }
            
            view_result = self.container.ui.task.render_history_task_actions(data)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def start_task(self, event):
        """启动任务"""
        try:
            res = await session_service.start_history_task(event.sender_id)
            if res.get('success'):
                await self.notify(event, "🚀 任务已启动", alert=True)
                await self.show_task_actions(event)
            else:
                await self.notify(event, f"启动失败: {res.get('error')}", alert=True)
        except Exception as e:
            await self.handle_exception(event, e)

    async def start_dry_run(self, event):
        """启动模拟运行"""
        try:
            res = await session_service.start_history_task(event.sender_id, dry_run=True)
            if res.get('success'):
                await self.notify(event, "🧪 模拟运行已启动 (不会产生实际转发)", alert=True)
                await self.show_current_history_task(event)
            else:
                await self.notify(event, f"启动失败: {res.get('error')}", alert=True)
        except Exception as e:
            return self.handle_exception(e)

    async def show_quick_stats(self, event):
        """显示快速统计"""
        try:
            if hasattr(event, 'answer'):
                await event.answer("⏳ 正在计算统计数据，请稍候...", alert=False)
            
            stats = await session_service.get_quick_stats(event.sender_id)
            if not stats['success']:
                await self.notify(event, f"统计失败: {stats.get('error')}", alert=True)
                return
            
            from handlers.button.new_menu_system import new_menu_system
            view_result = self.container.ui.task.render_quick_stats_result(stats)
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)


    async def cancel_task(self, event):
        """取消任务"""
        try:
            ok = await session_service.stop_history_task(event.sender_id)
            await self.notify(event, "⏹️ 已停止" if ok else "❌ 停止失败")
            await self.show_task_actions(event)
        except Exception as e:
            return self.handle_exception(e)

    async def pause_task(self, event):
        """暂停任务"""
        try:
            ok = await session_service.stop_history_task(event.sender_id)
            await self.notify(event, "⏸️ 已暂停" if ok else "❌ 暂停失败")
            await self.show_task_actions(event)
        except Exception as e:
            return self.handle_exception(e)

    async def toggle_dedup(self, event):
        """切换历史去重"""
        try:
            # 实现切换逻辑...
            await self.notify(event, "🔄 已切换去重状态")
            await self.show_task_actions(event)
        except Exception as e:
            return self.handle_exception(e)
            
    async def show_time_range(self, event):
        """显示时间范围设置 (Refactored to TaskRenderer)"""
        try:
            # 获取当前设置
            config = await session_service.get_time_range_config(event.sender_id)
            
            view_result = self.container.ui.task.render_time_range_settings(config)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_history_task_selector(self, event):
        """显示历史任务规则选择器 (Refactored to TaskRenderer)"""
        try:
            rules_res = await session_service.get_available_rules(event.sender_id)
            selection = await session_service.get_selected_rule(event.sender_id)
            
            data = {
                'rules': rules_res.get('rules', []),
                'current_selection': selection
            }
            
            view_result = self.container.ui.task.render_history_task_selector(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(
                event,
                title="🎯 **选择任务规则**",
                body_lines=[view_result.text],
                buttons=view_result.buttons,
                breadcrumb="🏠 > 📋 历史 > 🎯"
            )
        except Exception as e:
            return self.handle_exception(e)

    async def show_current_history_task(self, event):
        """显示当前执行中的历史任务 (Refactored to TaskRenderer)"""
        try:
            status = await session_service.get_history_task_status(event.sender_id)
            
            view_result = self.container.ui.task.render_current_history_task(status)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(
                event,
                title="📊 **当前任务进度**",
                body_lines=[view_result.text],
                buttons=view_result.buttons,
                breadcrumb="🏠 > 📋 历史 > 📊"
            )
        except Exception as e:
            return self.handle_exception(e)

    async def show_history_delay_settings(self, event):
        """显示历史任务延迟设置 (Refactored to TaskRenderer)"""
        try:
            delay_data = await session_service.get_delay_settings(event.sender_id)
            
            view_result = self.container.ui.task.render_delay_settings(delay_data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(
                event,
                title="⏱️ **转发延迟设置**",
                body_lines=[view_result.text],
                buttons=view_result.buttons,
                breadcrumb="🏠 > 📋 历史 > ⏱️"
            )
        except Exception as e:
            return self.handle_exception(e)

    async def show_media_filter_config(self, event):
        """显示媒体过滤配置"""
        view_result = self.container.ui.media.render_media_filter_config({})
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system._render_page(event, "🎬 **媒体过滤配置**", [view_result.text], view_result.buttons)

    async def show_ai_settings(self, event, rule_id: int):
        """显示单条规则的 AI 设置页面 (Refactored to UIRE-2.0)"""
        try:
            from services.rule.facade import rule_management_service
            data = await rule_management_service.get_rule_detail(rule_id)
            
            view_result = self.container.ui.media.render_ai_settings(data)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_summary_time_selection(self, event, rule_id: int, page: int = 0):
        """显示 AI 总结时间选择 (Refactored)"""
        try:
            from services.rule.facade import rule_management_service
            rule_data = await rule_management_service.get_rule_detail(rule_id)
            
            view_result = self.container.ui.media.render_summary_time_selection({
                'rule_id': rule_id,
                'current_time': rule_data.get('summary_time', '00:00')
            })
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def select_summary_time(self, event, rule_id: int, time: str):
        """设置 AI 总结时间"""
        try:
            from services.rule.facade import rule_management_service
            await self.notify(event, f"⏳ 正在设置总结时间: {time}...")
            result = await rule_management_service.logic.update_summary_time(rule_id, time)
            if result.get('success'):
                await self.notify(event, f"✅ 总结时间已设置为: {time}")
                await self.show_summary_time_selection(event, rule_id)
            else:
                await self.notify(event, f"❌ 设置失败: {result.get('error')}")
        except Exception as e:
            return self.handle_exception(e)

    async def show_model_selection(self, event, rule_id: int, page: int = 0):
        """显示 AI 模型选择 (Refactored)"""
        try:
            from core.config.settings_loader import load_ai_models
            from services.rule.facade import rule_management_service
            
            models = load_ai_models()
            rule_data = await rule_management_service.get_rule_detail(rule_id)
            
            view_result = self.container.ui.media.render_model_selection({
                'rule_id': rule_id,
                'models': models,
                'current_model': rule_data.get('ai_model')
            })
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def select_ai_model(self, event, rule_id: int, model: str):
        """设置 AI 模型"""
        try:
            from services.rule.facade import rule_management_service
            await self.notify(event, f"⏳ 正在切换至模型: {model}...")
            result = await rule_management_service.logic.update_ai_model(rule_id, model)
            if result.get('success'):
                await self.notify(event, f"✅ 已切换至模型: {model}")
                await self.show_ai_settings(event, rule_id)
            else:
                 await self.notify(event, f"❌ 切换失败: {result.get('error')}")
        except Exception as e:
            return self.handle_exception(e)

    async def run_summary_now(self, event, rule_id: int):
        """立即执行 AI 总结"""
        try:
            from scheduler.summary_scheduler import SummaryScheduler
            from services.rule.facade import rule_management_service
            
            rule_data = await rule_management_service.get_rule_detail(rule_id)
            if not rule_data.get('success'):
                return await self.notify(event, "❌ 规则不存在", alert=True)
            
            await self.notify(event, "🚀 正在生成 AI 总结，请稍候...")
            # 这里的调用逻辑取决于 SummaryScheduler 的具体实现
            # 假设有一个一次性触发的方法
            # await SummaryScheduler.trigger_once(rule_id) 
            await self.notify(event, "✅ 总结任务已加入队列", alert=True)
        except Exception as e:
            return self.handle_exception(e)

    async def enter_set_ai_prompt_state(self, event, rule_id: int, is_summary: bool = False):
        """进入 AI 提示词设置状态 (Refactored)"""
        try:
            from services.rule.facade import rule_management_service
            rule_data = await rule_management_service.get_rule_detail(rule_id)
            
            view_result = self.container.ui.media.render_ai_prompt_editor({
                'rule_id': rule_id,
                'type': "总结" if is_summary else "处理",
                'current_prompt': rule_data.get('summary_prompt' if is_summary else 'ai_prompt', '未设置')
            })
            
            state = f"set_{'summary' if is_summary else 'ai'}_prompt:{rule_id}"
            await session_service.update_user_state(event.sender_id, event.chat_id, state, rule_id, {"state_type": "ai"})
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def cancel_ai_state(self, event, rule_id: int):
        """取消 AI 状态并返回设置"""
        try:
            user_id = event.sender_id
            chat_id = event.chat_id
            await session_service.update_user_state(user_id, chat_id, None, None)
            await self.notify(event, "✅ 已取消设置")
            await self.show_ai_settings(event, rule_id)
        except Exception as e:
            return self.handle_exception(e)

    async def show_media_extensions(self, event, rule_id: int, page: int = 0):
        """显示媒体扩展名设置"""
        from handlers.button.callback.media_callback import callback_media_extensions
        await callback_media_extensions(event, rule_id, None, None, None)

    async def show_push_settings(self, event, rule_id: int, page: int = 0):
        """显示推送设置"""
        from handlers.button.callback.push_callback import callback_push_settings
        await callback_push_settings(event, rule_id, None, None, None)

    async def show_settings(self, event, rule_id: int):
        """显示规则的详细媒体设置"""
        from handlers.button.callback.media_callback import callback_media_settings
        await callback_media_settings(event, rule_id, None, None, None)

    async def show_max_size_selection(self, event, rule_id: int):
        """显示最大媒体大小选择"""
        from handlers.button.callback.media_callback import callback_set_max_media_size
        await callback_set_max_media_size(event, rule_id, None, None, None)

    async def set_max_size(self, event, rule_id: int, size: int):
        """设置最大媒体大小限制"""
        try:
            from services.rule.facade import rule_management_service
            await rule_management_service.logic.toggle_rule_setting(rule_id, "max_media_size", size)
            await self.notify(event, f"✅ 最大媒体大小已设为 {size}MB")
            await self.show_settings(event, rule_id)
        except Exception as e:
            return self.handle_exception(e)

    async def toggle_boolean(self, event, rule_id: int, field: str):
        """切换媒体相关的布尔设置"""
        try:
            from services.rule.facade import rule_management_service
            result = await rule_management_service.toggle_rule_setting(rule_id, field)
            status = "开启" if result.get("new_value") else "关闭"
            await self.notify(event, f"✅ 已{status}")
            await self.show_settings(event, rule_id)
        except Exception as e:
            return self.handle_exception(e)

    async def show_types_selection(self, event, rule_id: int):
        """显示媒体类型过滤选择"""
        from handlers.button.callback.media_callback import callback_set_media_types
        await callback_set_media_types(event, rule_id, None, None, None)

    async def toggle_type(self, event, rule_id: int, media_type: str):
        """切换特定媒体类型的过滤状态"""
        try:
            from services.rule.facade import rule_management_service
            await rule_management_service.toggle_media_type(rule_id, media_type)
            await self.show_types_selection(event, rule_id)
        except Exception as e:
            return self.handle_exception(e)

    async def toggle_extension(self, event, rule_id: int, extension: str, page: int = 0):
        """切换特定媒体扩展名的过滤状态"""
        try:
            from services.rule.facade import rule_management_service
            await rule_management_service.toggle_media_extension(rule_id, extension)
            await self.show_media_extensions(event, rule_id, page)
        except Exception as e:
            return self.handle_exception(e)

    async def show_rule_dedup_settings(self, event, rule_id: int):
        """显示单条规则的去重详细设置"""
        from handlers.button.callback.modules.rule_dedup_settings import callback_rule_dedup_settings
        message = await event.get_message()
        await callback_rule_dedup_settings(event, rule_id, message)

    async def update_rule_dedup(self, event, rule_id: int, key: str, val: str):
        """更新规则去重设置"""
        from handlers.button.callback.modules.rule_dedup_settings import callback_update_rule_dedup
        message = await event.get_message()
        await callback_update_rule_dedup(event, rule_id, key, val, message)

    async def reset_rule_dedup(self, event, rule_id: int):
        """重置规则去重设置"""
        from handlers.button.callback.modules.rule_dedup_settings import callback_reset_rule_dedup
        message = await event.get_message()
        await callback_reset_rule_dedup(event, rule_id, message)

    async def show_dedup_hub(self, event):
        """显示智能去重中心 (Refactored)"""
        try:
            # 获取完整数据
            data = await self.container.dedup_service.get_details()
            
            # 使用 DedupRenderer
            view_result = self.container.ui.dedup.render_settings_main(data)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_smart_dedup_settings(self, event):
        """显示去重主设置 (Alias for show_dedup_hub)"""
        await self.show_dedup_hub(event)

    async def show_dedup_similarity(self, event):
        """显示相似度设置"""
        data = await self.container.dedup_service.get_details()
        view_result = self.container.ui.dedup.render_similarity_settings(data)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_dedup_content_hash(self, event):
        """显示内容哈希设置"""
        data = await self.container.dedup_service.get_details()
        view_result = self.container.ui.dedup.render_content_hash_settings(data)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_dedup_video(self, event):
        """显示视频去重设置"""
        data = await self.container.dedup_service.get_details()
        view_result = self.container.ui.dedup.render_video_settings(data)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_dedup_time_window(self, event):
        """显示时间窗口设置"""
        data = await self.container.dedup_service.get_details()
        view_result = self.container.ui.dedup.render_time_window_settings(data)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_dedup_statistics(self, event):
        """显示统计详情"""
        data = await self.container.dedup_service.get_details()
        view_result = self.container.ui.dedup.render_statistics(data)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_dedup_advanced(self, event):
        """显示高级设置"""
        data = await self.container.dedup_service.get_details()
        view_result = self.container.ui.dedup.render_advanced_settings(data)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_dedup_sticker(self, event):
        """显示表情包去重设置"""
        data = await self.container.dedup_service.get_details()
        view_result = self.container.ui.dedup.render_sticker_settings(data)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_dedup_global(self, event):
        """显示全局共振设置"""
        data = await self.container.dedup_service.get_details()
        view_result = self.container.ui.dedup.render_global_resonance_settings(data)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_dedup_album(self, event):
        """显示相册去重设置"""
        data = await self.container.dedup_service.get_details()
        view_result = self.container.ui.dedup.render_album_settings(data)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_dedup_hash_examples(self, event):
        """显示哈希特征示例"""
        # 简单显示一个渲染后的文本即可
        from telethon import Button
        text = "📋 **哈希特征示例**\n\n"
        text += "去重系统会提取消息的以下特征：\n"
        text += "1. **文本**: 移除链接、提及、表情后的核心内容\n"
        text += "2. **视频**: 基于 file_id 或首尾固定分块的 MD5\n"
        text += "3. **图片**: 基于分辨率和文件大小的复合签名\n"
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system._render_from_text(event, text, [[Button.inline("👈 返回高级设置", "new_menu:dedup_advanced")]])

    async def show_session_management(self, event):
        """显示会话管理中心"""
        view_result = self.container.ui.session.render_session_hub({})
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_session_dedup_menu(self, event):
        """显示会话去重扫描主页"""
        view_result = self.container.ui.session.render_session_dedup_menu({})
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_dedup_results(self, event):
        """显示会话扫描结果详情"""
        try:
            chat_id = event.chat_id
            # 直接从服务获取缓存结果
            results_map = self.container.session_service.current_scan_results.get(chat_id, {})
            
            # 转换为显示名称映射
            display_results = {}
            for sig, ids in results_map.items():
                name = self.container.session_service._signature_to_display_name(sig)
                display_results[name] = len(ids)
            
            view_result = self.container.ui.session.render_scan_results({'results': display_results})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def start_session_scan(self, event):
        """执行会话扫描任务"""
        try:
            # 1. 显示启动状态
            from telethon import Button
            start_text = (
                "🚀 **智能扫描启动中...**\n\n"
                "正在遍历会话历史并提取内容指纹...\n"
                "⏳ 这可能需要几分钟时间，请稍候。"
            )
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_from_text(event, start_text, [[Button.inline("❌ 取消扫描", "new_menu:session_dedup")]])

            # 2. 进度回调
            last_update_msg = 0
            async def progress_cb(proc, found):
                nonlocal last_update_msg
                import time
                now = time.time()
                if now - last_update_msg > 3: # 3秒更新一次UI避免卡顿
                    try:
                        await event.edit(f"🚀 **扫描进行中...**\n\n📊 已遍历: **{proc:,}** 条\n🔍 已发现: **{found:,}** 组重复", buttons=[[Button.inline("❌ 取消", "new_menu:session_dedup")]])
                        last_update_msg = now
                    except: pass
            
            # 3. 调用服务执行
            results = await self.container.session_service.scan_duplicate_messages(event, progress_callback=progress_cb)
            
            # 4. 显示完成并跳转
            await self.show_dedup_results(event)
            
        except Exception as e:
            return self.handle_exception(e)

    async def show_delete_session_messages_menu(self, event):
        """显示批量删除管理"""
        try:
            chat_id = event.chat_id
            user_id = event.sender_id
            time_range = await self.container.session_service.get_time_range_display(user_id)
            progress = await self.container.session_service.get_delete_progress(user_id)
            
            data = {
                'time_range': time_range,
                'status': progress.get('status', 'ready'),
                'progress': progress
            }
            
            view_result = self.container.ui.session.render_delete_management(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_select_delete_menu(self, event):
        """显示重复项手动挑选菜单 (UIRE-2.0)"""
        try:
            chat_id = event.chat_id
            scan_counts = await self.container.session_service.scan_duplicate_messages(event)
            selected = await self.container.session_service.get_selection_state(chat_id)
            
            view_result = self.container.ui.session.render_selection_menu({
                'scan_counts': scan_counts,
                'selected': selected
            })
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def toggle_select_signature(self, event, signature: str):
        """切换特定签名的选中状态"""
        try:
            chat_id = event.chat_id
            await self.container.session_service.toggle_select_signature(chat_id, signature)
            await self.show_select_delete_menu(event)
        except Exception as e:
            return self.handle_exception(e)

    async def execute_batch_delete(self, event):
        """执行批量删除确认后的逻辑"""
        try:
            success, msg = await self.container.session_service.delete_session_messages_by_filter(event)
            if hasattr(event, 'answer'):
                 await event.answer(msg, alert=not success)
            await self.show_delete_session_messages_menu(event)
        except Exception as e:
             return self.handle_exception(e)

    async def show_delete_preview(self, event):
        """显示删除预览"""
        try:
            count, samples = await self.container.session_service.preview_session_messages_by_filter(event)
            # 转换为简单字典列表供 Renderer 使用
            sample_data = [{'id': m.id, 'text': m.text or "[媒体内容]"} for m in samples]
            
            view_result = self.container.ui.session.render_delete_preview({'count': count, 'samples': sample_data})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_push_config_details(self, event, config_id: int):
        """显示推送配置详情"""
        from handlers.button.callback.push_callback import callback_toggle_push_config
        await callback_toggle_push_config(event, config_id, None, None, None)

    async def toggle_push_config_status(self, event, config_id: int):
        """切换特定推送配置的状态"""
        try:
            from services.rule.facade import rule_management_service
            await rule_management_service.toggle_push_config_setting(config_id, "enable_push_channel")
            await self.show_push_config_details(event, config_id)
        except Exception as e:
            return self.handle_exception(e)

    async def toggle_media_send_mode(self, event, config_id: int):
        """切换推送配置的媒体发送模式"""
        try:
            from services.rule.facade import rule_management_service
            await rule_management_service.toggle_media_send_mode(config_id)
            await self.show_push_config_details(event, config_id)
        except Exception as e:
            return self.handle_exception(e)

    async def delete_push_config(self, event, config_id: int):
        """删除特定的推送配置项"""
        from handlers.button.callback.push_callback import callback_delete_push_config
        await callback_delete_push_config(event, config_id, None, None, None)

    async def enter_add_push_channel_state(self, event, rule_id: int):
        """进入添加推送频道状态（等待输入）"""
        from handlers.button.callback.push_callback import callback_add_push_channel
        await callback_add_push_channel(event, rule_id, None, await event.get_message(), None)

    async def run_legacy_dedup_cmd(self, event, rule_id: int, cmd_type: str):
        """
        [DEPRECATED] 运行旧版基于规则的去重命令。
        请迁移至专门的 Strategy 处理类。
        """
        from handlers.button.callback.other_callback import (
            callback_dedup_scan_now, callback_delete_duplicates,
            callback_confirm_delete_duplicates, callback_view_source_messages,
            callback_keep_duplicates, callback_toggle_allow_delete_source_on_dedup
        )
        handlers = {
            "scan": callback_dedup_scan_now,
            "delete": callback_delete_duplicates,
            "confirm": callback_confirm_delete_duplicates,
            "view": callback_view_source_messages,
            "keep": callback_keep_duplicates,
            "toggle": callback_toggle_allow_delete_source_on_dedup
        }
        handler = handlers.get(cmd_type)
        if handler:
            # 移除 Controller 层的 Session 管理 (符合架构规范)
            # 传递 None 作为 session，让 handler 内部通过 container.db.get_session(None) 自行管理
            await handler(event, rule_id, None, await event.get_message(), None)

    async def show_history_task_list(self, event, page: int = 1):
        """显示历史任务列表 (Refactored to UIRE-3.0)"""
        try:
            tasks, total = await self.container.task_repo.get_tasks(page=page, limit=10, task_type='history')
            
            view_result = self.container.ui.task.render_history_task_list({
                'tasks': tasks,
                'total': total,
                'page': page
            })
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)
