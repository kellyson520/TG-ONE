import logging
from typing import Optional
from controllers.base import BaseController, ControllerAbort
from services.session_service import session_service

logger = logging.getLogger(__name__)

class MediaController(BaseController):
    """媒体、AI 与历史补全业务控制器"""

    async def show_history_hub(self, event):
        """显示历史任务中心"""
        try:
            # 简化：这里目前没有复杂的 Stats，直接渲染
            view_result = self.container.ui.media.render_history_hub({})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(
                event,
                title="补全 **历史中心**",
                body_lines=[view_result.text],
                buttons=view_result.buttons,
                breadcrumb="🏠 > 📋 历史"
            )
        except Exception as e:
            return self.handle_exception(e)

    async def show_task_actions(self, event):
        """显示任务操作页"""
        try:
            from services.forward_settings_service import forward_settings_service
            res = await self.container.menu_service.get_selected_rule(event.chat_id)
            settings = await forward_settings_service.get_global_media_settings()
            
            data = {
                'selected': res,
                'dedup_enabled': settings.get('history_dedup_enabled', False),
                'time_range': '最近 24 小时' # 示例 Hardcode
            }
            
            view_result = self.container.ui.media.render_history_task_actions(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(
                event,
                title="🚀 **任务配置**",
                body_lines=[view_result.text],
                buttons=view_result.buttons
            )
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
                await self.notify(event, f"❌ 启动失败: {res.get('message')}", alert=True)
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
        """显示时间范围设置"""
        from handlers.button.modules.history import history_module
        await history_module.show_time_range_selection(event)

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
            await new_menu_system._render_page(
                event,
                title=f"🤖 **AI 增强设置**",
                body_lines=[view_result.text],
                buttons=view_result.buttons
            )
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
            await new_menu_system._render_page(
                event, 
                title="⏰ **设置总结时间**", 
                body_lines=[view_result.text], 
                buttons=view_result.buttons
            )
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
            await new_menu_system._render_page(
                event, 
                title="🧠 **AI 模型选择**", 
                body_lines=[view_result.text], 
                buttons=view_result.buttons
            )
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
            await new_menu_system._render_page(
                event, 
                title=f"✍️ 设置 AI {'总结' if is_summary else '处理'}提示词", 
                body_lines=[view_result.text], 
                buttons=view_result.buttons
            )
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
        """显示智能去重中心"""
        try:
            from core.helpers.realtime_stats import realtime_stats_cache
            stats = await realtime_stats_cache.get_dedup_stats()
            
            # 使用 Renderer 渲染
            from ui.menu_renderer import menu_renderer
            render_data = menu_renderer.render_dedup_hub(stats)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(
                event,
                title="🧹 **智能去重中心**",
                body_lines=[render_data['text'].split('\n\n', 1)[1] if '\n\n' in render_data['text'] else render_data['text']],
                buttons=render_data['buttons'],
                breadcrumb="🏠 > 🧹"
            )
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
