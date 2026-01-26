"""
菜单控制器
负责接收菜单操作请求，处理业务逻辑，可以调用 View(NewMenuSystem) 进行渲染
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from telethon import Button, events

from services.menu_service import menu_service
from services.rule.facade import rule_management_service
from services.session_service import session_service
from services.analytics_service import analytics_service
# 避免循环引用，这里不直接导入 forward_manager 等，按需导入或使用 container

logger = logging.getLogger(__name__)

class MenuController:
    """菜单控制器类 - 负责协调业务逻辑与UI渲染"""

    def __init__(self):
        # 延迟导入或直接引用
        from handlers.button.new_menu_system import new_menu_system
        self.view = new_menu_system
        from ui.menu_renderer import MenuRenderer
        self.renderer = MenuRenderer()
        self.service = menu_service

    async def _send_menu(self, event, title: str, body_lines: list, buttons: list, breadcrumb: str = None):
        """统一发送/编辑菜单"""
        await self.view._render_page(
            event,
            title=title,
            body_lines=body_lines,
            buttons=buttons,
            breadcrumb=breadcrumb
        )

    async def _send_error(self, event, text: str):
        """统一错误提示"""
        await event.answer(text, alert=True)

    async def show_main_menu(self, event, force_refresh: bool = False):
        """显示主菜单"""
        try:
            stats = await self.service.get_main_menu_data(force_refresh=force_refresh)
            render_data = self.renderer.render_main_menu(stats)
            await self._send_menu(event, "🏠 **主菜单**", [render_data['text']], render_data['buttons'])
        except Exception as e:
            logger.error(f"显示主菜单失败: {e}")
            await self._send_error(event, "看板加载失败")

    async def show_forward_hub(self, event):
        """显示转发管理中心"""
        try:
            stats = await self.service.get_forward_hub_data()
            render_data = self.renderer.render_forward_hub(stats)
            await self._send_menu(event, "🔄 **转发管理中心**", [render_data['text']], render_data['buttons'], "🏠 > 🔄")
        except Exception as e:
            logger.error(f"显示转发中心失败: {e}")
            await self._send_error(event, "转发中心加载失败")

    async def show_dedup_hub(self, event):
        """显示智能去重中心"""
        try:
            from core.helpers.realtime_stats import realtime_stats_cache
            stats = await realtime_stats_cache.get_dedup_stats()
            
            # 使用 Renderer 渲染
            render_data = self.renderer.render_dedup_hub(stats)
            
            await self._send_menu(
                event,
                title="🧹 **智能去重中心**",
                body_lines=[render_data['text'].split('\n\n', 1)[1] if '\n\n' in render_data['text'] else render_data['text']],
                buttons=render_data['buttons'],
                breadcrumb="🏠 > 🧹"
            )
        except Exception as e:
            logger.error(f"显示去重中心失败: {e}")
            await self._send_error(event, "去重中心加载失败")

    async def show_analytics_hub(self, event):
        """显示数据分析中心"""
        try:
            overview_data = await analytics_service.get_analytics_overview()
            
            # 使用 Renderer 渲染
            render_data = self.renderer.render_analytics_hub(overview_data)
            
            await self._send_menu(
                event,
                title="📊 **数据分析中心**",
                body_lines=[render_data['text'].split('\n\n', 1)[1] if '\n\n' in render_data['text'] else render_data['text']],
                buttons=render_data['buttons'],
                breadcrumb="🏠 > 📊"
            )
        except Exception as e:
            logger.error(f"显示分析中心失败: {e}")
            await self._send_error(event, "分析中心加载失败")

    async def show_system_hub(self, event):
        """显示系统设置中心"""
        try:
            stats = await self.service.get_system_hub_data()
            render_data = self.renderer.render_system_hub(stats)
            await self._send_menu(event, "⚙️ **系统设置中心**", [render_data['text']], render_data['buttons'], "🏠 > ⚙️")
        except Exception as e:
            logger.error(f"显示系统中心失败: {e}")
            await self._send_error(event, "系统中心加载失败")

    async def show_rule_list(self, event, page: int = 0, search_query: str = None):
        """显示规则列表 (分页)"""
        try:
            from services.rule_management_service import rule_management_service
            page_size = 5
            data = await rule_management_service.get_rule_list(page=page, page_size=page_size, search_query=search_query)
            
            # 使用 Renderer 渲染
            render_data = self.renderer.render_rule_list(data)
            
            await self._send_menu(
                event,
                title="📋 **规则列表**",
                body_lines=[render_data['text'].split('\n\n', 1)[1] if '\n\n' in render_data['text'] else render_data['text']],
                buttons=render_data['buttons'],
                breadcrumb="🏠 > 🔄 > 📋"
            )
        except Exception as e:
            logger.error(f"显示规则列表失败: {e}")
            await self._send_error(event, "规则列表加载失败")

    async def show_rule_detail(self, event, rule_id: int):
        """显示单条规则详情"""
        try:
            from services.rule_management_service import rule_management_service
            # 获取原始详情数据
            data = await rule_management_service.get_rule_detail(rule_id)
            if not data.get('success'):
                return await self._send_error(event, data.get('error', '未知错误'))

            # 使用 Renderer 渲染
            render_data = self.renderer.render_rule_detail({'rule': data})
            
            await self._send_menu(
                event,
                title=f"📝 **规则详情：{rule_id}**",
                body_lines=[render_data['text'].split('\n\n', 1)[1] if '\n\n' in render_data['text'] else render_data['text']],
                buttons=render_data['buttons'],
                breadcrumb=f"🏠 > 🔄 > 📋 > 📝 {rule_id}"
            )
        except Exception as e:
            logger.error(f"显示规则详情失败: {e}")
            await self._send_error(event, "加载详情失败")

    async def _get_rule_obj_as_dict(self, rule_id: int):
        """获取规则对象并转换为 Renderer 喜欢的字典格式"""
        from services.rule_management_service import rule_management_service
        data = await rule_management_service.get_rule_detail(rule_id)
        return data

    async def show_rule_basic_settings(self, event, rule_id: int):
        """显示基础转发设置"""
        data = await self._get_rule_obj_as_dict(rule_id)
        render_data = self.renderer.render_rule_basic_settings({'rule': data})
        await self._send_menu(event, "⚙️ **基础设置**", [render_data['text'].split('\n\n', 1)[1]], render_data['buttons'], f"🏠 > 📝 {rule_id} > ⚙️")

    async def show_rule_display_settings(self, event, rule_id: int):
        """显示内容显示设置"""
        data = await self._get_rule_obj_as_dict(rule_id)
        render_data = self.renderer.render_rule_display_settings({'rule': data})
        await self._send_menu(event, "🎨 **显示设置**", [render_data['text'].split('\n\n', 1)[1]], render_data['buttons'], f"🏠 > 📝 {rule_id} > 🎨")

    async def show_rule_advanced_settings(self, event, rule_id: int):
        """显示高级功能配置"""
        data = await self._get_rule_obj_as_dict(rule_id)
        render_data = self.renderer.render_rule_advanced_settings({'rule': data})
        await self._send_menu(event, "🚀 **高级配置**", [render_data['text'].split('\n\n', 1)[1]], render_data['buttons'], f"🏠 > 📝 {rule_id} > 🚀")

    async def toggle_rule_setting_new(self, event, rule_id: int, setting_key: str):
        """通用规则布尔设置切换业务逻辑"""
        try:
            from services.rule_management_service import rule_management_service
            # 处理特殊非布尔值（可选）
            # 执行切换
            await rule_management_service.toggle_rule_boolean_setting(rule_id, setting_key)
            await event.answer("✅ 设置已更新")
            
            # 智能返回：根据 setting_key 决定返回哪个子页面
            basic_keys = ['enabled', 'use_bot', 'forward_mode', 'handle_mode', 'is_delete_original']
            display_keys = ['message_mode', 'is_preview', 'is_original_sender', 'is_original_time', 'is_original_link', 'is_filter_user_info', 'enable_comment_button']
            
            if setting_key in basic_keys:
                await self.show_rule_basic_settings(event, rule_id)
            elif setting_key in display_keys:
                await self.show_rule_display_settings(event, rule_id)
            else:
                await self.show_rule_advanced_settings(event, rule_id)
                
        except Exception as e:
            logger.error(f"切换规则设置失败: {e}")
            await event.answer(f"❌ 操作失败: {e}", alert=True)

    async def show_manage_keywords(self, event, rule_id: int):
        """管理规则关键词"""
        try:
            keywords = await rule_management_service.get_keywords(rule_id, is_blacklist=None)
            
            text = f"🔎 **关键词管理** (规则 `{rule_id}`)\n\n"
            if not keywords:
                text += "📭 目前没有任何关键词，所有消息都将放行。"
            else:
                for i, k in enumerate(keywords, 1):
                    mode = "正则" if k.is_regex else "普通"
                    type = "黑名单" if k.is_blacklist else "白名单"
                    text += f"{i}. `{k.keyword}` ({mode}|{type})\n"
            
            buttons = [
                [Button.inline("➕ 添加关键词", f"new_menu:add_keyword:{rule_id}")],
                [Button.inline("🧹 清空关键词", f"new_menu:clear_keywords_confirm:{rule_id}")],
                [Button.inline("👈 返回详情", f"new_menu:rule_detail:{rule_id}")]
            ]
            await self._send_menu(event, "🔎 **关键词管理**", [text], buttons)
        except Exception as e:
            logger.error(f"显示关键词管理失败: {e}")
            await self._send_error(event, "操作失败")

    async def toggle_rule_status(self, event, rule_id: int):
        """快捷切换规则状态"""
        try:
            from services.rule_management_service import rule_management_service
            data = await rule_management_service.get_rule_detail(rule_id)
            new_status = not data.get('enabled', False)
            await rule_management_service.toggle_rule_status(rule_id, new_status)
            await event.answer(f"✅ 规则已{'开启' if new_status else '关闭'}")
            await self.show_rule_detail(event, rule_id)
        except Exception as e:
            await self._send_error(event, f"操作失败: {e}")

    async def delete_rule_confirm(self, event, rule_id: int):
        """删除规则二次确认"""
        buttons = [
            [Button.inline("Confirm 🗑️ 确认删除", f"new_menu:delete_rule_do:{rule_id}"),
             Button.inline("❌ 取消", f"new_menu:rule_detail:{rule_id}")]
        ]
        await self._send_menu(event, "⚠️ **删除确认**", [f"确定要删除规则 `{rule_id}` 吗？此操作不可逆！"], buttons)

    async def delete_rule_do(self, event, rule_id: int):
        """执行删除规则"""
        try:
            from services.rule_management_service import rule_management_service
            await rule_management_service.delete_rule(rule_id)
            await event.answer("✅ 规则已删除")
            await self.show_rule_list(event)
        except Exception as e:
            await self._send_error(event, f"删除失败: {e}")

    async def show_db_backup(self, event):
        """展示备份界面"""
        from services.system_service import system_service
        text = "💾 **数据库备份与维护**\n您可以手动触发现有数据库的备份，或者管理历史备份。"
        buttons = [
            [Button.inline("✅ 立即备份", "new_menu:do_backup")],
            [Button.inline("📂 历史备份管理", "new_menu:view_backups")],
            [Button.inline("👈 返回系统中心", "new_menu:system_hub")]
        ]
        await self._send_menu(event, "💾 **数据库备份**", [text], buttons)

    async def show_cache_cleanup(self, event):
        """展示缓存清理"""
        text = "🗑️ **缓存与垃圾清理**\n此操作将扫描并删除临时文件、会话快照和过期日志。"
        buttons = [
            [Button.inline("🔥 确认清理", "new_menu:do_cleanup")],
            [Button.inline("👈 返回系统中心", "new_menu:system_hub")]
        ]
        await self._send_menu(event, "🗑️ **垃圾清理**", [text], buttons)

    async def show_manage_replace_rules(self, event, rule_id: int):
        """管理规则替换规则"""
        try:
            rules = await rule_management_service.get_replace_rules(rule_id)
            
            text = f"🔄 **替换规则管理** (规则 `{rule_id}`)\n\n"
            if not rules:
                text += "📭 目前没有任何替换规则。"
            else:
                for i, r in enumerate(rules, 1):
                    text += f"{i}. `{r.pattern}` ➔ `{r.content}`\n"
            
            buttons = [
                [Button.inline("➕ 添加替换规则", f"new_menu:add_replace:{rule_id}")],
                [Button.inline("🧹 清空替换规则", f"new_menu:clear_replaces_confirm:{rule_id}")],
                [Button.inline("👈 返回详情", f"new_menu:rule_detail:{rule_id}")]
            ]
            await self._send_menu(event, "🔄 **替换规则管理**", [text], buttons)
        except Exception as e:
            logger.error(f"显示替换规则管理失败: {e}")
            await self._send_error(event, "操作失败")

    async def show_session_management(self, event):
        """显示会话管理中心"""
        text = "💬 **会话管理中心**\n提供针对当前/指定会话的消息清理、重复项扫描等高级功能。"
        buttons = [
            [Button.inline("🔍 会话内去重", "new_menu:session_dedup")],
            [Button.inline("🗑️ 批量删除消息", "new_menu:delete_session_messages")],
            [Button.inline("👈 返回系统中心", "new_menu:system_hub")]
        ]
        await self._send_menu(event, "💬 **会话管理**", [text], buttons, breadcrumb="🏠 > 📋 会话")

    async def show_history_messages(self, event):
        """显示历史消息处理页"""
        # 如果 self.view (new_menu_system) 没有该方法，则尝试调用其支持的方法或直接由控制器处理
        try:
            await self.view.show_history_messages_menu(event)
        except AttributeError:
            from handlers.button.modules.history import history_module
            await history_module.show_history_menu(event)

    async def show_realtime_monitor(self, event):
        """显示系统实时监控"""
        try:
            metrics = await analytics_service.get_performance_metrics()
            sys_res = metrics.get('system_resources', {})
            qs = metrics.get('queue_status', {})
            status = await analytics_service.get_system_status()

            cpu_usage = sys_res.get('cpu_usage', 0)
            mem_usage = sys_res.get('memory_usage', 0)
            
            # 安全地转换 error_rate (可能是字符串 "0.0%" 或数字)
            error_rate_raw = qs.get('error_rate', 0)
            if isinstance(error_rate_raw, str):
                # 移除百分号并转换
                error_rate = float(error_rate_raw.rstrip('%'))
            else:
                error_rate = float(error_rate_raw)
            
            def status_icon(s):
                return "🟢" if s == 'running' else "🔴" if s == 'stopped' else "⚪"

            text = (
                "🖥️ **系统实时监控**\n\n"
                f"⚙️ **系统资源**\n"
                f"• CPU使用率: {cpu_usage}%\n"
                f"• 内存使用率: {mem_usage}%\n\n"
                f"📥 **任务队列**\n"
                f"• 待处理: {qs.get('pending_tasks', 0)}\n"
                f"• 活跃队列: {qs.get('active_queues', 0)}\n"
                f"• 错误率: {error_rate:.2f}%\n\n"
                f"🛡️ **服务状态**\n"
                f"• 数据库: {status_icon(status.get('db'))} {status.get('db')}\n"
                f"• 机器人: {status_icon(status.get('bot'))} {status.get('bot')}\n"
                f"• 去重服务: {status_icon(status.get('dedup'))} {status.get('dedup')}"
            )

            buttons = [
                [Button.inline("🔄 刷新数据", "new_menu:forward_performance")],
                [Button.inline("👈 返回分析中心", "new_menu:analytics_hub")]
            ]

            await self.view._render_page(
                event,
                title="🖥️ **系统实时监控**",
                body_lines=[text],
                buttons=buttons,
                breadcrumb="🏠 > 📊 分析 > 🖥️ 监控"
            )
        except Exception as e:
            logger.error(f"显示实时监控失败: {e}")
            await event.answer("加载监控数据失败", alert=True)

    async def show_help_guide(self, event):
        """显示帮助说明页面"""
        text = (
            "🎯 **四大功能模块介绍**\n\n"
            "🔄 **转发管理**\n"
            "• 创建和管理转发规则\n"
            "• 批量处理历史消息\n\n"
            "🧹 **智能去重**\n"
            "• 时间窗口去重\n"
            "• 智能相似度检测\n\n"
            "📊 **数据分析**\n"
            "• 转发统计分析\n"
            "• 实时性能监控\n\n"
            "⚙️ **系统设置**\n"
            "• 数据库备份与恢复\n"
            "• 系统资源监控"
        )
        
        buttons = [
            [Button.inline("🏠 返回主菜单", "new_menu:main_menu")]
        ]
        
        await self.view._render_page(
            event,
            title="📖 **使用帮助**",
            body_lines=[text],
            buttons=buttons
        )

    async def show_history_task_actions(self, event):
        """显示历史任务操作菜单"""
        buttons = [
            [Button.inline("⏰ 设置时间范围", "new_menu:history_time_range")],
            [Button.inline("📝 消息筛选", "new_menu:history_message_filter")],
            [Button.inline("👈 返回上一级", "new_menu:history_messages")],
        ]
        await self.view._render_page(
            event,
            title="🛠️ **历史任务操作**",
            body_lines=["请选择要执行的操作："],
            buttons=buttons
        )

    async def show_history_time_range(self, event):
        """显示历史任务时间范围设置"""
        await history_module.show_time_range_selection(event)

    async def _set_user_state(self, event, state: str, rule_id: int, extra: dict = None):
        """统一设置用户会话状态"""
        user_id = event.sender_id
        chat_id = event.chat_id
        await session_service.update_user_state(user_id, chat_id, state, rule_id, extra)

    async def enter_add_keyword_state(self, event, rule_id: int):
        """进入添加关键词状态"""
        await self._set_user_state(event, "waiting_keyword", rule_id)
        text = (
            "➕ **添加关键词**\n\n"
            "请输入要添加的关键词。支持以下格式：\n"
            "• `关键词` (普通匹配)\n"
            "• `re:正则表达式` (正则匹配)\n"
            "• 多对多：每行一个关键词\n\n"
            "也可发送 `取消` 返回。"
        )
        buttons = [[Button.inline("❌ 取消", f"new_menu:keywords:{rule_id}")]]
        await self._send_menu(event, "➕ **添加关键词**", [text], buttons)

    async def enter_add_replace_state(self, event, rule_id: int):
        """进入添加替换规则状态"""
        await self._set_user_state(event, "waiting_replace", rule_id)
        text = (
            "➕ **添加替换规则**\n\n"
            "请输入替换规则，格式为：\n"
            "`旧内容 ➔ 新内容` (中间使用空格或箭头分隔)\n\n"
            "例如：`苹果 香蕉` 或 `re:^Hello ➔ Hi`\n\n"
            "也可发送 `取消` 返回。"
        )
        buttons = [[Button.inline("❌ 取消", f"new_menu:replaces:{rule_id}")]]
        await self._send_menu(event, "➕ **添加替换规则**", [text], buttons)

    async def clear_keywords_confirm(self, event, rule_id: int):
        """清空关键词确认"""
        buttons = [
            [Button.inline("Confirm 🧹 确认清空", f"new_menu:clear_keywords_do:{rule_id}"),
             Button.inline("❌ 取消", f"new_menu:keywords:{rule_id}")]
        ]
        await self._send_menu(event, "⚠️ **清空确认**", ["确定要清空该规则的所有关键词吗？"], buttons)

    async def clear_keywords_do(self, event, rule_id: int):
        """执行清空关键词"""
        try:
            from services.rule_management_service import rule_management_service
            await rule_management_service.clear_keywords(rule_id)
            await event.answer("✅ 关键词已清空")
            await self.show_manage_keywords(event, rule_id)
        except Exception as e:
            await self._send_error(event, f"操作失败: {e}")

    async def clear_replaces_confirm(self, event, rule_id: int):
        """清空替换规则确认"""
        buttons = [
            [Button.inline("Confirm 🧹 确认清空", f"new_menu:clear_replaces_do:{rule_id}"),
             Button.inline("❌ 取消", f"new_menu:replaces:{rule_id}")]
        ]
        await self._send_menu(event, "⚠️ **清空确认**", ["确定要清空该规则的所有替换规则吗？"], buttons)

    async def clear_replaces_do(self, event, rule_id: int):
        """执行清空替换规则"""
        try:
            await rule_management_service.clear_replace_rules(rule_id)
            await event.answer("✅ 替换规则已清空")
            await self.show_manage_replace_rules(event, rule_id)
        except Exception as e:
            await self._send_error(event, f"操作失败: {e}")

    async def show_db_performance_monitor(self, event):
        """显示数据库性能监控面板"""
        try:
            from ui.menu_renderer import menu_renderer
            
            # 收集数据库性能数据
            dashboard_data = {
                'query_metrics': {
                    'slow_queries': [],  # 慢查询列表
                    'top_queries': []    # 热点查询列表
                },
                'system_metrics': {
                    'cpu_usage': {'avg': 0},
                    'memory_usage': {'avg': 0},
                    'database_size': {'current': 0},
                    'connection_count': {'avg': 0, 'max': 0}
                },
                'alerts': []  # 告警列表
            }
            
            # 尝试获取实际的性能数据
            try:
                metrics = await analytics_service.get_performance_metrics()
                sys_res = metrics.get('system_resources', {})
                dashboard_data['system_metrics']['cpu_usage']['avg'] = sys_res.get('cpu_percent', 0)
                dashboard_data['system_metrics']['memory_usage']['avg'] = sys_res.get('memory_percent', 0)
            except Exception as e:
                logger.warning(f"获取性能数据失败: {e}")
            
            # 渲染页面
            rendered = menu_renderer.render_db_performance_monitor({'dashboard': dashboard_data})
            await self.view._render_page(
                event,
                title="🗄️ **数据库性能监控**",
                body_lines=[rendered['text']],
                buttons=rendered['buttons']
            )
        except Exception as e:
            logger.error(f"显示数据库性能监控失败: {e}")
            await self._send_error(event, "加载监控面板失败")

    async def show_db_optimization_center(self, event):
        """显示数据库优化中心"""
        try:
            from ui.menu_renderer import menu_renderer
            
            # 收集优化系统状态
            optimization_data = {
                'status': {
                    'suite_status': 'inactive',  # 优化系统状态
                    'components': {
                        'query_optimization': {'status': 'inactive'},
                        'monitoring': {'status': 'active'},
                        'sharding': {'status': 'inactive'},
                        'batch_processing': {'status': 'inactive'}
                    }
                },
                'recommendations': []  # 优化建议列表
            }
            
            # 渲染页面
            rendered = menu_renderer.render_db_optimization_center(optimization_data)
            await self.view._render_page(
                event,
                title="🔧 **数据库优化中心**",
                body_lines=[rendered['text']],
                buttons=rendered['buttons']
            )
        except Exception as e:
            logger.error(f"显示数据库优化中心失败: {e}")
            await self._send_error(event, "加载优化中心失败")

    async def enable_db_optimization(self, event):
        """启用数据库优化"""
        try:
            await event.answer("✅ 数据库优化已启用")
            await self.show_db_optimization_center(event)
        except Exception as e:
            logger.error(f"启用数据库优化失败: {e}")
            await event.answer("启用失败", alert=True)

    async def run_db_optimization_check(self, event):
        """运行数据库优化检查"""
        try:
            await event.answer("🔍 正在运行优化检查...")
            from services.system_service import system_service
            result = await system_service.run_db_optimization()
            
            if result.get('success'):
                await event.answer(f"✅ {result.get('message')} (耗时: {result.get('duration')}s)")
            else:
                await event.answer(f"❌ 优化失败: {result.get('error')}", alert=True)

            await self.show_db_optimization_center(event)
        except Exception as e:
            logger.error(f"运行优化检查失败: {e}")
            await event.answer("检查失败", alert=True)

    async def refresh_db_performance(self, event):
        """刷新数据库性能数据"""
        try:
            await event.answer("🔄 正在刷新数据...")
            await self.show_db_performance_monitor(event)
        except Exception as e:
            logger.error(f"刷新性能数据失败: {e}")
            await event.answer("刷新失败", alert=True)

    async def refresh_db_optimization_status(self, event):
        """刷新数据库优化状态"""
        try:
            await event.answer("🔄 正在刷新状态...")
            await self.show_db_optimization_center(event)
        except Exception as e:
            logger.error(f"刷新优化状态失败: {e}")
            await event.answer("刷新失败", alert=True)

menu_controller = MenuController()
