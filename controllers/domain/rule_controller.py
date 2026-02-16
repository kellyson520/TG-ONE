import logging
from typing import Optional
from telethon import Button
from controllers.base import BaseController, ControllerAbort
from services.rule.facade import rule_management_service

logger = logging.getLogger(__name__)

class RuleController(BaseController):
    """规则管理业务控制器"""

    async def list_rules(self, event, page: int = 0, search_query: str = None):
        """显示规则列表"""
        try:
            page_size = 5
            data = await rule_management_service.get_rule_list(page=page, page_size=page_size, search_query=search_query)
            
            # 使用新的 ViewResult 渲染流程
            view_result = self.container.ui.rule.render_rule_list(data)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_detail(self, event, rule_id: int):
        """显示规则详情"""
        try:
            data = await rule_management_service.get_rule_detail(rule_id)
            if not data.get('success', True): # CRUD usually returns success: False on error
                 raise ControllerAbort(data.get('error', '获取规则失败'))

            view_result = self.container.ui.rule.render_rule_detail({'rule': data})
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e, back_target="new_menu:list_rules:0")

    async def toggle_status(self, event, rule_id: int, from_page: str = 'detail', page: int = 0):
        """切换规则启用状态"""
        try:
            data = await rule_management_service.get_rule_detail(rule_id)
            new_status = not data.get('enabled', False)
            await rule_management_service.toggle_rule_status(rule_id, new_status)
            await self.notify(event, f"✅ 规则 {rule_id} 已{'开启' if new_status else '关闭'}")
            
            if from_page == 'multi':
                await self.show_multi_source_management(event, page)
            else:
                await self.show_detail(event, rule_id)
        except Exception as e:
            return self.handle_exception(e)

    async def toggle_setting(self, event, rule_id: int, field: str):
        """通用布尔设置切换"""
        try:
            await rule_management_service.toggle_rule_boolean_setting(rule_id, field)
            await self.notify(event, "✅ 设置已更新")
            
            # 返回对应的设置子页面
            basic_keys = ['use_bot', 'forward_mode', 'handle_mode', 'is_delete_original']
            display_keys = ['message_mode', 'is_preview', 'is_original_sender', 'is_original_time', 'is_original_link', 'is_filter_user_info', 'enable_comment_button']
            media_keys = ['enable_duration_filter', 'enable_resolution_filter', 'enable_file_size_range']
            ai_keys = ['is_ai', 'is_summary', 'is_top_summary']
            
            if field in basic_keys:
                await self.show_basic_settings(event, rule_id)
            elif field in display_keys:
                await self.show_display_settings(event, rule_id)
            elif field in media_keys:
                await self.show_media_settings(event, rule_id)
            elif field in ai_keys:
                await self.show_ai_settings(event, rule_id)
            else:
                await self.show_advanced_settings(event, rule_id)
        except Exception as e:
            return self.handle_exception(e)

    async def show_basic_settings(self, event, rule_id: int):
        """基础设置页"""
        data = await rule_management_service.get_rule_detail(rule_id)
        view_result = self.container.ui.rule.render_rule_basic_settings({'rule': data})
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_display_settings(self, event, rule_id: int):
        """显示设置页"""
        data = await rule_management_service.get_rule_detail(rule_id)
        view_result = self.container.ui.rule.render_rule_display_settings({'rule': data})
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def show_advanced_settings(self, event, rule_id: int):
        """高级设置页"""
        data = await rule_management_service.get_rule_detail(rule_id)
        view_result = self.container.ui.rule.render_rule_advanced_settings({'rule': data})
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.display_view(event, view_result)

    async def delete_confirm(self, event, rule_id: int):
        """删除确认"""
        from telethon import Button
        buttons = [
            [Button.inline("Confirm 🗑️ 确认删除", f"new_menu:delete_rule_do:{rule_id}"),
             Button.inline("❌ 取消", f"new_menu:rule_detail:{rule_id}")]
        ]
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system._render_page(event, "⚠️ **删除确认**", [f"确定要删除规则 `{rule_id}` 吗？此操作不可逆！"], buttons)

    async def delete_do(self, event, rule_id: int):
        """执行删除"""
        try:
            await rule_management_service.delete_rule(rule_id)
            await self.notify(event, "✅ 规则已删除")
            await self.list_rules(event)
        except Exception as e:
            return self.handle_exception(e)

    async def show_keywords(self, event, rule_id: int):
        """显示关键词管理"""
        try:
            keywords = await rule_management_service.get_keywords(rule_id, is_blacklist=None)
            view_result = self.container.ui.rule.render_manage_keywords({'rule_id': rule_id, 'keywords': keywords})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_replaces(self, event, rule_id: int):
        """显示替换规则管理"""
        try:
            rules = await rule_management_service.get_replace_rules(rule_id)
            view_result = self.container.ui.rule.render_manage_replace_rules({'rule_id': rule_id, 'replace_rules': rules})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_copy_selection(self, event, rule_id: int, page: int = 0):
        """显示复制规则目标选择"""
        from handlers.button.button_helpers import create_copy_rule_buttons
        buttons = await create_copy_rule_buttons(rule_id, page=page)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system._render_page(event, "📋 **复制规则设置**", ["请选择要将当前规则配置复制到的目标规则："], buttons)

    async def perform_copy(self, event, source_id: int, target_id: int):
        """执行规则复制"""
        try:
            await self.notify(event, "⏳ 正在复制规则...")
            result = await rule_management_service.copy_rule(source_id, target_id)
            if result.get('success'):
                await self.notify(event, "✅ 规则复制成功")
                await self.show_copy_selection(event, source_id)
            else:
                raise ControllerAbort(result.get('error', '复制失败'))
        except Exception as e:
            return self.handle_exception(e)

    async def show_other_settings(self, event, rule_id: int):
        """显示其他杂项设置"""
        from handlers.button.callback.other_callback import callback_other_settings
        await callback_other_settings(event, rule_id, None, None, None)

    async def handle_ufb_item(self, event, item_type: str):
        """处理 UFB 绑定项切换"""
        from handlers.button.callback.other_callback import callback_handle_ufb_item
        data = f"ufb_item:{item_type}"
        await callback_handle_ufb_item(event, None, None, None, data)

    async def _set_user_state(self, event, state: str, rule_id: int, extra: dict = None):
        """统一设置用户会话状态"""
        user_id = event.sender_id
        chat_id = event.chat_id
        from services.session_service import session_service
        await session_service.update_user_state(user_id, chat_id, state, rule_id, extra)

    async def enter_add_keyword_state(self, event, rule_id: int):
        """进入添加关键词状态"""
        await self._set_user_state(event, f"kw_add:{rule_id}", rule_id)
        text = (
            "➕ **添加关键词**\n\n"
            "请输入要添加的关键词。支持以下格式：\n"
            "• `关键词` (普通匹配)\n"
            "• `re:正则表达式` (正则匹配)\n"
            "• 多对多：每行一个关键词\n\n"
            "也可发送 `取消` 返回。"
        )
        buttons = [[Button.inline("❌ 取消", f"new_menu:keywords:{rule_id}")]]
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system._render_page(event, "➕ **添加关键词**", [text], buttons)

    async def enter_add_replace_state(self, event, rule_id: int):
        """进入添加替换规则状态"""
        await self._set_user_state(event, f"rr_add:{rule_id}", rule_id)
        text = (
            "➕ **添加替换规则**\n\n"
            "请输入替换规则，格式为：\n"
            "`旧内容 ➔ 新内容` (中间使用空格或箭头分隔)\n\n"
            "例如：`苹果 香蕉` 或 `re:^Hello ➔ Hi`\n\n"
            "也可发送 `取消` 返回。"
        )
        buttons = [[Button.inline("❌ 取消", f"new_menu:replaces:{rule_id}")]]
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system._render_page(event, "➕ **添加替换规则**", [text], buttons)

    async def clear_keywords_confirm(self, event, rule_id: int):
        """清空关键词确认"""
        buttons = [
            [Button.inline("Confirm 🗑️ 确确认清空", f"new_menu:clear_keywords_do:{rule_id}"),
             Button.inline("❌ 取消", f"new_menu:keywords:{rule_id}")]
        ]
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system._render_page(event, "⚠️ **清空确认**", ["确定要清空该规则的所有关键词吗？"], buttons)

    async def execute_clear_keywords(self, event, rule_id: int):
        """执行清空关键词"""
        try:
            await rule_management_service.clear_keywords(rule_id)
            await self.notify(event, "✅ 关键词已全部清空")
            await self.show_keywords(event, rule_id)
        except Exception as e:
            return self.handle_exception(e)

    async def execute_clear_replaces(self, event, rule_id: int):
        """执行清空替换规则"""
        try:
            await rule_management_service.clear_replace_rules(rule_id)
            await self.notify(event, "✅ 替换规则已清空")
            await self.show_replaces(event, rule_id)
        except Exception as e:
            return self.handle_exception(e)

    async def show_rule_statistics(self, event):
        """显示规则运行统计数据"""
        try:
            stats = await rule_management_service.get_rule_statistics()
            text = "📊 **规则运行统计**\n\n"
            text += f"总规则数: {stats.get('total_count', 0)}\n有效规则: {stats.get('active_count', 0)}\n"
            
            from telethon import Button
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(
                event,
                title="📊 **统计概览**",
                body_lines=[text],
                buttons=[[Button.inline("👈 返回", "new_menu:analytics_hub")]]
            )
        except Exception as e:
             return self.handle_exception(e)

    async def show_multi_source_management(self, event, page: int = 0):
        """显示多源管理中心"""
        from handlers.button.modules.rules_menu import rules_menu
        await rules_menu.show_multi_source_management(event, page)

    async def show_multi_source_detail(self, event, rule_id: int):
        """显示多源规则详情"""
        from handlers.button.modules.rules_menu import rules_menu
        await rules_menu.show_multi_source_detail(event, rule_id)

    async def show_rule_status(self, event, rule_id: int):
        """显示规则状态页面"""
        from handlers.button.modules.rules_menu import rules_menu
        await rules_menu.show_rule_status(event, rule_id)

    async def show_sync_config(self, event, rule_id: int):
        """显示规则同步配置"""
        from handlers.button.modules.rules_menu import rules_menu
        await rules_menu.show_sync_config(event, rule_id)

    async def show_media_settings(self, event, rule_id: int):
        """显示媒体设置页"""
        try:
            data = await rule_management_service.get_rule_detail(rule_id)
            view_result = self.container.ui.rule.render_media_settings({'rule': data})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_ai_settings(self, event, rule_id: int):
        """显示 AI 设置页"""
        try:
            data = await rule_management_service.get_rule_detail(rule_id)
            view_result = self.container.ui.rule.render_ai_settings({'rule': data})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def enter_set_value_state(self, event, rule_id: int, key: str):
        """进入设置数值或文本的状态"""
        field_names = {
            'max_media_size': '最大文件限制 (MB)',
            'ai_model': 'AI 模型名称',
            'ai_prompt': 'AI 重写提示词',
            'summary_time': '定时总结时间 (HH:mm)',
            'summary_prompt': '总结提示词',
            'delay_seconds': '延迟处理秒数'
        }
        name = field_names.get(key, key)
        await self._set_user_state(event, f"set_val:{rule_id}:{key}", rule_id)
        
        text = f"请输入 **{name}** 的新值。完成后按回车发送即可。\n\n也可发送 `取消` 直接返回。"
        buttons = [[Button.inline("❌ 取消", f"new_menu:rule_detail:{rule_id}")]]
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system._render_page(event, f"📝 设置 {name}", [text], buttons)

    async def show_sync_rule_picker(self, event, rule_id: int, page: int = 0):
        """显示同步规则选择器"""
        from handlers.button.button_helpers import create_sync_rule_buttons
        buttons = await create_sync_rule_buttons(rule_id, page=page)
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system._render_page(
            event, 
            "🔗 **同步目标管理**", 
            ["请选择要同步状态的目标规则：\n(开启后，源规则转发成功会自动激活目标规则)"], 
            buttons,
            breadcrumb=f"🏠 > 📝 {rule_id} > 🔗 > ⚙️"
        )

    async def toggle_rule_sync(self, event, rule_id: int, target_id: int, page: int):
        """切换同步关系"""
        try:
            await rule_management_service.toggle_rule_sync(rule_id, target_id)
            await self.notify(event, "✅ 同步状态已更新")
            await self.show_sync_rule_picker(event, rule_id, page)
        except Exception as e:
            return self.handle_exception(e)
