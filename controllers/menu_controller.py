"""
菜单控制器
负责接收菜单操作请求，处理业务逻辑，可以调用 View(NewMenuSystem) 进行渲染
"""
import asyncio
import logging
from telethon import Button, events
from telethon.errors import FloodWaitError

from services.menu_service import menu_service
from services.session_service import session_service
from .base import ControllerAbort
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
        from core.container import container
        self.container = container

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
        try:
            # 如果是回调查询（点击按钮触发），可以使用 answer (弹窗通知)
            if hasattr(event, 'answer'):
                await event.answer(text, alert=True)
            else:
                # 如果是普通消息（命令触发），使用 respond 回复
                await event.respond(f"❌ {text}")
        except Exception as e:
            logger.warning(f"发送错误提示失败: {e}")

    async def show_main_menu(self, event, force_refresh: bool = False):
        """显示主菜单"""
        try:
            # 兼容性：创建临时控制器实例以进行维护检查
            from controllers.domain.admin_controller import AdminController
            admin_ctrl = AdminController(self.container)
            await admin_ctrl.check_maintenance(event)
            
            stats = await self.service.get_main_menu_data(force_refresh=force_refresh)
            render_data = self.renderer.render_main_menu(stats)
            await self._send_menu(event, "🏠 **主菜单**", [render_data['text']], render_data['buttons'])
        except FloodWaitError as e:
            logger.error(f"显示主菜单触发流控: 需要等待 {e.seconds} 秒")
        except Exception as e:
            if isinstance(e, ControllerAbort):
                 return await self.container.ui.render_error(e.message, e.back_target)
            logger.error(f"显示主菜单失败: {e}")
            await self._send_error(event, "看板加载失败")

    async def show_forward_hub(self, event, force_refresh: bool = False):
        """显示转发管理中心"""
        try:
            from controllers.domain.admin_controller import AdminController
            admin_ctrl = AdminController(self.container)
            await admin_ctrl.check_maintenance(event)

            stats = await self.service.get_forward_hub_data(force_refresh=force_refresh)
            render_data = self.renderer.render_forward_hub(stats)
            await self._send_menu(event, "🔄 **转发管理中心**", [render_data['text']], render_data['buttons'], "🏠 > 🔄")
        except Exception as e:
            if isinstance(e, ControllerAbort):
                 return await self.container.ui.render_error(e.message, e.back_target)
            logger.error(f"显示转发中心失败: {e}")
            await self._send_error(event, "转发中心加载失败")

    async def show_dedup_hub(self, event):
        """显示智能去重中心"""
        await self.container.media_controller.show_dedup_hub(event)

    async def show_analytics_hub(self, event):
        """显示数据分析中心"""
        await self.container.admin_controller.show_analytics_hub(event)

    async def show_forward_analytics(self, event):
        """显示转发统计详情"""
        await self.container.admin_controller.show_forward_analytics(event)

    async def show_system_hub(self, event):
        """显示系统设置中心"""
        await self.container.admin_controller.show_system_hub(event)

    async def show_rule_list(self, event, page: int = 0, search_query: str = None):
        """显示规则列表 (分页)"""
        await self.container.rule_controller.list_rules(event, page=page, search_query=search_query)

    async def show_rule_detail(self, event, rule_id: int):
        """显示单条规则详情"""
        await self.container.rule_controller.show_detail(event, rule_id)


    async def show_rule_basic_settings(self, event, rule_id: int):
        """显示基础转发设置"""
        await self.container.rule_controller.show_basic_settings(event, rule_id)

    async def show_rule_display_settings(self, event, rule_id: int):
        """显示内容显示设置"""
        await self.container.rule_controller.show_display_settings(event, rule_id)

    async def show_rule_advanced_settings(self, event, rule_id: int):
        """显示高级功能配置"""
        await self.container.rule_controller.show_advanced_settings(event, rule_id)

    async def toggle_rule_setting_new(self, event, rule_id: int, setting_key: str):
        """通用规则布尔设置切换业务逻辑"""
        await self.container.rule_controller.toggle_setting(event, rule_id, setting_key)

    async def show_manage_keywords(self, event, rule_id: int):
        """管理规则关键词"""
        await self.container.rule_controller.show_keywords(event, rule_id)

    async def toggle_rule_status(self, event, rule_id: int):
        """快捷切换规则状态"""
        await self.container.rule_controller.toggle_status(event, rule_id)

    async def delete_rule_confirm(self, event, rule_id: int):
        """删除规则二次确认"""
        await self.container.rule_controller.delete_confirm(event, rule_id)

    async def delete_rule_do(self, event, rule_id: int):
        """执行删除规则"""
        await self.container.rule_controller.delete_do(event, rule_id)

    async def show_db_backup(self, event):
        """展示备份界面"""
        await self.container.admin_controller.show_backup_management(event)

    async def show_cache_cleanup(self, event):
        """展示缓存清理"""
        await self.container.admin_controller.show_cache_cleanup(event)

    async def show_manage_replace_rules(self, event, rule_id: int):
        """管理规则替换规则"""
        await self.container.rule_controller.show_replaces(event, rule_id)


    async def show_history_messages(self, event):
        """显示历史消息处理页"""
        # 如果 self.view (new_menu_system) 没有该方法，则尝试调用其支持的方法或直接由控制器处理
        try:
            await self.view.show_history_messages_menu(event)
        except AttributeError:
            from handlers.button.modules.history import history_module
            await history_module.show_history_messages(event)

    async def show_realtime_monitor(self, event):
        """显示系统实时监控"""
        await self.container.admin_controller.show_realtime_monitor(event)

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

    async def show_faq(self, event):
        """显示常见问题"""
        try:
            render_data = self.renderer.render_faq()
            await self._send_menu(
                event,
                title="❓ **常见问题**",
                body_lines=[render_data['text']],
                buttons=render_data['buttons'],
                breadcrumb="🏠 > 📖 > ❓"
            )
        except Exception as e:
            logger.error(f"加载FAQ失败: {e}")
            await self._send_error(event, "加载失败")

    async def show_detailed_docs(self, event):
        """显示详细文档"""
        try:
            render_data = self.renderer.render_detailed_docs()
            await self._send_menu(
                event,
                title="📖 **详细文档**",
                body_lines=[render_data['text']],
                buttons=render_data['buttons'],
                breadcrumb="🏠 > 📖 > 📚"
            )
        except Exception as e:
            logger.error(f"加载详细文档失败: {e}")
            await self._send_error(event, "加载失败")

    async def show_history_task_actions(self, event):
        """显示历史任务操作菜单 (增强版)"""
        await self.container.media_controller.show_task_actions(event)
    async def show_history_time_range(self, event):
        """显示历史任务时间范围设置"""
        await self.container.media_controller.show_time_range(event)

    async def _set_user_state(self, event, state: str, rule_id: int, extra: dict = None):
        """统一设置用户会话状态"""
        user_id = event.sender_id
        chat_id = event.chat_id
        await session_service.update_user_state(user_id, chat_id, state, rule_id, extra)

    async def enter_add_keyword_state(self, event, rule_id: int):
        """进入添加关键词状态"""
        await self.container.rule_controller.enter_add_keyword_state(event, rule_id)

    async def enter_add_replace_state(self, event, rule_id: int):
        """进入添加替换规则状态"""
        await self.container.rule_controller.enter_add_replace_state(event, rule_id)

    async def clear_keywords_confirm(self, event, rule_id: int):
        """清空关键词确认"""
        await self.container.rule_controller.clear_keywords_confirm(event, rule_id)

    async def clear_keywords_do(self, event, rule_id: int):
        """执行清空关键词"""
        await self.container.rule_controller.execute_clear_keywords(event, rule_id)

    async def clear_replaces_confirm(self, event, rule_id: int):
        """清空替换规则确认"""
        await self.container.rule_controller.clear_replaces_confirm(event, rule_id)

    async def clear_replaces_do(self, event, rule_id: int):
        """执行清空替换规则"""
        await self.container.rule_controller.execute_clear_replaces(event, rule_id)

    async def show_db_performance_monitor(self, event):
        """显示数据库性能监控面板"""
        await self.container.admin_controller.show_performance_monitor(event)

    async def show_db_optimization_center(self, event):
        """显示数据库优化中心"""
        await self.container.admin_controller.show_optimization_center(event)

    async def enable_db_optimization(self, event):
        """启用数据库优化"""
        await self.container.admin_controller.show_optimization_center(event)

    async def run_db_optimization_check(self, event):
        """运行数据库优化检查"""
        await self.container.admin_controller.run_optimization_check(event)

    async def refresh_db_performance(self, event):
        """刷新数据库性能数据"""
        await self.container.admin_controller.show_performance_monitor(event)

    async def refresh_db_optimization_status(self, event):
        """刷新数据库优化状态"""
        await self.container.admin_controller.show_optimization_center(event)

    async def show_db_query_analysis(self, event):
        """显示数据库查询分析"""
        await self.container.admin_controller.show_db_query_analysis(event)

    async def show_db_performance_trends(self, event):
        """显示数据库性能趋势"""
        await self.container.admin_controller.show_db_performance_trends(event)

    async def show_db_alert_management(self, event):
        """显示数据库告警管理"""
        await self.container.admin_controller.show_db_alert_management(event)

    async def show_db_optimization_advice(self, event):
        """显示优化建议"""
        await self.container.admin_controller.show_db_optimization_advice(event)

    async def show_db_detailed_report(self, event):
        """显示详细数据库报告"""
        await self.container.admin_controller.show_db_detailed_report(event)

    async def show_db_optimization_config(self, event):
        """显示优化配置"""
        await self.container.admin_controller.show_db_optimization_config(event)

    async def show_db_index_analysis(self, event):
        """显示索引分析"""
        await self.container.admin_controller.show_db_index_analysis(event)

    async def show_db_cache_management(self, event):
        """显示缓存管理"""
        await self.container.admin_controller.show_db_cache_management(event)

    async def show_db_optimization_logs(self, event):
        """显示优化日志"""
        await self.container.admin_controller.show_db_optimization_logs(event)

    async def show_rule_management(self, event, page=0):
        """显示规则管理菜单 (转发管理中心)"""
        await self.view.show_rule_management(event, page)

    async def rebuild_bloom_index(self, event):
        """重启 Bloom 索引系统"""
        await self.container.admin_controller.rebuild_bloom_index(event)

    async def run_db_archive_once(self, event):
        """运行一次性归档"""
        await self.container.admin_controller.run_archive_once(event)

    async def run_db_archive_force(self, event):
        """运行强制归档"""
        await self.container.admin_controller.run_archive_force(event)

    # --- 历史数据处理 ---
    async def show_history_task_selector(self, event):
        """显示历史任务选择器"""
        await self.view.show_history_task_selector(event)

    async def show_current_history_task(self, event):
        """显示当前执行中的历史任务"""
        await self.view.show_current_history_task(event)

    async def start_history_task(self, event):
        """启动历史迁移任务"""
        await self.container.media_controller.start_task(event)

    async def cancel_history_task(self, event):
        """取消历史迁移任务"""
        await self.container.media_controller.cancel_task(event)

    async def pause_history_task(self, event):
        """暂停历史任务"""
        await self.container.media_controller.pause_task(event)

    async def resume_history_task(self, event):
        """恢复历史任务"""
        await self.container.media_controller.start_task(event)

    async def show_history_task_list(self, event):
        """显示历史任务列表"""
        await event.answer("🚧 列表功能正在集成中")

    async def run_db_reindex(self, event):
        """执行数据库重建索引"""
        await self.container.admin_controller.run_reindex(event)

    async def clear_db_alerts(self, event):
        """清除数据库告警"""
        await self.container.admin_controller.clear_alerts(event)

    async def clear_dedup_cache(self, event):
        """清除去重缓存"""
        await self.container.admin_controller.clear_dedup_cache(event)

    async def toggle_history_dedup(self, event):
        """切换历史任务去重"""
        await self.container.media_controller.toggle_dedup(event)

    async def show_current_chat_rules(self, event, chat_id: str):
        """显示当前会话的规则列表"""
        await self.container.rule_controller.list_rules(event, search_query=str(chat_id))

    async def show_current_chat_rules_page(self, event, chat_id: str, page: int):
        """显示当前会话的规则列表 (分页)"""
        await self.container.rule_controller.list_rules(event, page=page, search_query=str(chat_id))

    async def show_rule_statistics(self, event):
        """显示规则统计数据"""
        await self.container.rule_controller.show_rule_statistics(event)

    async def show_multi_source_management(self, event, page: int = 0):
        """显示多源管理中心"""
        await self.container.rule_controller.show_multi_source_management(event, page)

    async def show_multi_source_detail(self, event, rule_id: int):
        """显示多源规则详情"""
        await self.container.rule_controller.show_multi_source_detail(event, rule_id)

    async def show_rule_status(self, event, rule_id: int):
        """显示规则状态"""
        await self.container.rule_controller.show_rule_status(event, rule_id)

    async def show_sync_config(self, event, rule_id: int):
        """显示同步配置"""
        await self.container.rule_controller.show_sync_config(event, rule_id)

    # --- AI 设置相关 ---
    async def show_ai_settings(self, event, rule_id: int):
        """显示 AI 设置页面"""
        await self.container.media_controller.show_ai_settings(event, rule_id)

    async def show_summary_time_selection(self, event, rule_id: int, page: int = 0):
        """显示 AI 总结时间选择"""
        await self.container.media_controller.show_summary_time_selection(event, rule_id, page)

    async def select_summary_time(self, event, rule_id: int, time: str):
        """设置 AI 总结时间"""
        await self.container.media_controller.select_summary_time(event, rule_id, time)

    async def show_model_selection(self, event, rule_id: int, page: int = 0):
        """显示 AI 模型选择"""
        await self.container.media_controller.show_model_selection(event, rule_id, page)

    async def select_ai_model(self, event, rule_id: int, model: str):
        """设置 AI 模型"""
        await self.container.media_controller.select_ai_model(event, rule_id, model)

    async def run_summary_now(self, event, rule_id: int):
        """立即执行 AI 总结"""
        await self.container.media_controller.run_summary_now(event, rule_id)

    async def enter_set_ai_prompt_state(self, event, rule_id: int, is_summary: bool = False):
        """进入 AI 提示词设置状态"""
        await self.container.media_controller.enter_set_ai_prompt_state(event, rule_id, is_summary)

    async def cancel_ai_state(self, event, rule_id: int):
        """取消 AI 状态并返回设置"""
        await self.container.media_controller.cancel_ai_state(event, rule_id)

    # --- 管理员面板增强 ---
    async def show_admin_panel(self, event):
        """显示管理员面板"""
        await self.container.admin_controller.show_admin_panel(event)

    async def show_admin_logs(self, event):
        """显示运行日志"""
        await self.container.admin_controller.show_system_logs(event)

    async def show_admin_cleanup_menu(self, event):
        """显示清理维护菜单"""
        await self.container.admin_controller.show_admin_cleanup_menu(event)

    async def execute_admin_cleanup(self, event, days: int):
        """执行日志清理"""
        await self.container.admin_controller.execute_admin_cleanup_logs(event, days)

    async def execute_admin_cleanup_temp(self, event):
        """清理临时文件"""
        await self.container.admin_controller.execute_cleanup_temp(event)

    async def show_admin_stats(self, event):
        """显示统计报告"""
        await self.container.admin_controller.show_stats(event)

    async def toggle_maintenance_mode(self, event):
        """切换维护模式"""
        await self.container.admin_controller.toggle_maintenance_mode(event)

    async def show_admin_config(self, event):
        """显示系统配置"""
        await self.container.admin_controller.show_config(event)

    async def show_restart_confirm(self, event):
        """显示重启确认"""
        await self.container.admin_controller.show_restart_confirm(event)

    async def execute_restart(self, event):
        """执行重启"""
        await self.container.admin_controller.execute_restart(event)

    # --- 规则复制相关 ---
    async def show_copy_rule_selection(self, event, rule_id: int, page: int = 0):
        """显示复制规则目标选择"""
        await self.container.rule_controller.show_copy_selection(event, rule_id, page)

    async def perform_rule_copy(self, event, source_id: int, target_id: int):
        """执行规则复制"""
        await self.container.rule_controller.perform_copy(event, source_id, target_id)

    # --- 规则去重设置 ---
    async def show_rule_dedup_settings(self, event, rule_id: int):
        """显示单条规则的去重详细设置"""
        await self.container.media_controller.show_rule_dedup_settings(event, rule_id)

    async def update_rule_dedup(self, event, rule_id: int, key: str, val: str):
        """更新规则去重设置"""
        await self.container.media_controller.update_rule_dedup(event, rule_id, key, val)

    async def reset_rule_dedup(self, event, rule_id: int):
        """重置规则去重设置"""
        await self.container.media_controller.reset_rule_dedup(event, rule_id)

    async def run_legacy_dedup_cmd(self, event, rule_id: int, cmd_type: str):
        """
        [DEPRECATED] 运行旧版基于规则的去重命令。
        通过 MediaController 转发。
        """
        await self.container.media_controller.run_legacy_dedup_cmd(event, rule_id, cmd_type)

    async def run_admin_db_cmd(self, event, cmd_type: str):
        """运行数据库管理命令"""
        await self.container.admin_controller.run_admin_db_cmd(event, cmd_type)



    # --- 媒体设置 ---
    async def show_media_settings(self, event, rule_id: int):
        """显示规则的媒体设置"""
        await self.container.media_controller.show_settings(event, rule_id)

    async def show_max_media_size_selection(self, event, rule_id: int):
        """显示媒体大小选择"""
        await self.container.media_controller.show_max_size_selection(event, rule_id)

    async def set_max_media_size(self, event, rule_id: int, size: int):
        """设置最大媒体大小"""
        await self.container.media_controller.set_max_size(event, rule_id, size)

    async def toggle_media_boolean(self, event, rule_id: int, field: str):
        """切换媒体布尔设置"""
        await self.container.media_controller.toggle_boolean(event, rule_id, field)

    async def show_media_types_selection(self, event, rule_id: int):
        """显示媒体类型选择"""
        await self.container.media_controller.show_types_selection(event, rule_id)

    async def toggle_media_type(self, event, rule_id: int, media_type: str):
        """切换媒体类型过滤"""
        await self.container.media_controller.toggle_type(event, rule_id, media_type)

    async def show_media_extensions_page(self, event, rule_id: int, page: int = 0):
        """显示媒体扩展名选择页"""
        await self.container.media_controller.show_media_extensions(event, rule_id, page)

    async def toggle_media_extension(self, event, rule_id: int, extension: str, page: int = 0):
        """切换媒体后缀过滤"""
        await self.container.media_controller.toggle_extension(event, rule_id, extension, page)

    # --- 推送设置 ---
    async def show_push_settings(self, event, rule_id: int, page: int = 0):
        """显示规则推送设置"""
        await self.container.media_controller.show_push_settings(event, rule_id, page)

    async def toggle_push_boolean(self, event, rule_id: int, field: str):
        """切换推送布尔设置"""
        await self.container.media_controller.toggle_boolean(event, rule_id, field)

    async def show_push_config_details(self, event, config_id: int):
        """显示推送配置详情"""
        await self.container.media_controller.show_push_config_details(event, config_id)

    async def toggle_push_config_status(self, event, config_id: int):
        """切换推送配置状态"""
        await self.container.media_controller.toggle_push_config_status(event, config_id)

    async def toggle_media_send_mode(self, event, config_id: int):
        """切换媒体发送模式"""
        await self.container.media_controller.toggle_media_send_mode(event, config_id)

    async def delete_push_config(self, event, config_id: int):
        """删除推送配置"""
        await self.container.media_controller.delete_push_config(event, config_id)

    async def enter_add_push_channel_state(self, event, rule_id: int):
        """进入添加推送频道状态"""
        await self.container.media_controller.enter_add_push_channel_state(event, rule_id)


    async def show_other_settings(self, event, rule_id: int):
        """显示其他设置"""
        await self.container.rule_controller.show_other_settings(event, rule_id)

    async def handle_ufb_item(self, event, item_type: str):
        """处理 UFB 绑定项切换"""
        await self.container.rule_controller.handle_ufb_item(event, item_type)


    async def show_session_management(self, event):
        """显示会话管理中心"""
        await self.container.admin_controller.show_session_management(event)

    async def show_system_logs(self, event):
        """查看系统日志"""
        await self.container.admin_controller.show_system_logs(event)


menu_controller = MenuController()
