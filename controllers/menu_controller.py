"""
菜单控制器
负责接收菜单操作请求，处理业务逻辑，可以调用 View(NewMenuSystem) 进行渲染
此文件作为中央调度中心，将请求委派给 RuleController, MediaController, AdminController 等领域控制器。
"""
import asyncio
import logging
from telethon import Button, events
from telethon.errors import FloodWaitError

from services.menu_service import menu_service
from services.session_service import session_service
from .base import ControllerAbort

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
            if hasattr(event, 'answer'):
                await event.answer(text, alert=True)
            else:
                await event.respond(f"❌ {text}")
        except Exception as e:
            logger.warning(f"发送错误提示失败: {e}")

    def handle_exception(self, e):
        """统一异常处理"""
        logger.error(f"MenuController Error: {e}", exc_info=True)
        # 可以根据异常类型进行分流处理

    # --- 1. Base & Main Hubs ---

    async def show_main_menu(self, event, force_refresh: bool = False):
        """显示主菜单"""
        try:
            from controllers.domain.admin_controller import AdminController
            admin_ctrl = AdminController(self.container)
            await admin_ctrl.check_maintenance(event)
            
            stats = await self.service.get_main_menu_data(force_refresh=force_refresh)
            view_result = self.renderer.render_main_menu(stats)
            await self.view.display_view(event, view_result)
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
            view_result = self.renderer.render_forward_hub(stats)
            await self.view.display_view(event, view_result)
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

    async def show_system_hub(self, event):
        """显示系统设置中心"""
        await self.container.admin_controller.show_system_hub(event)

    async def show_help_guide(self, event):
        """显示帮助说明页面"""
        try:
            view_result = self.renderer.render_help_guide()
            await self.view.display_view(event, view_result)
        except Exception as e:
            logger.error(f"加载帮助菜单失败: {e}")
            await self._send_error(event, "加载失败")

    async def show_faq(self, event):
        """显示常见问题"""
        try:
            # Assume renderer has render_faq, otherwise provide default
            if hasattr(self.renderer, 'render_faq'):
                view_result = self.renderer.render_faq()
                await self.view.display_view(event, view_result)
            else:
                 await self._send_error(event, "FAQ 功能开发中")
        except Exception as e:
            logger.error(f"加载FAQ失败: {e}")

    async def show_detailed_docs(self, event):
        """显示详细文档"""
        try:
            if hasattr(self.renderer, 'render_detailed_docs'):
                view_result = self.renderer.render_detailed_docs()
                await self.view.display_view(event, view_result)
            else:
                await self._send_error(event, "详细文档开发中")
        except Exception as e:
            logger.error(f"加载详细文档失败: {e}")

    # --- 2. Smart Dedup Settings ---

    async def show_smart_dedup_settings(self, event):
        """显示去重主设置"""
        await self.container.media_controller.show_smart_dedup_settings(event)

    async def show_dedup_similarity(self, event):
        """显示相似度设置"""
        await self.container.media_controller.show_dedup_similarity(event)

    async def show_dedup_content_hash(self, event):
        """显示内容哈希设置"""
        await self.container.media_controller.show_dedup_content_hash(event)

    async def show_dedup_video(self, event):
        """显示视频去重设置"""
        await self.container.media_controller.show_dedup_video(event)

    async def show_dedup_time_window(self, event):
        """显示时间窗口设置"""
        await self.container.media_controller.show_dedup_time_window(event)

    async def show_dedup_statistics(self, event):
        """显示统计详情"""
        await self.container.media_controller.show_dedup_statistics(event)

    async def show_dedup_advanced(self, event):
        """显示高级设置"""
        await self.container.media_controller.show_dedup_advanced(event)

    async def show_dedup_sticker(self, event):
        """显示表情包去重设置"""
        await self.container.media_controller.show_dedup_sticker(event)

    async def show_dedup_global(self, event):
        """显示全局共振设置"""
        await self.container.media_controller.show_dedup_global(event)

    async def show_dedup_album(self, event):
        """显示相册去重设置"""
        await self.container.media_controller.show_dedup_album(event)

    async def show_dedup_hash_examples(self, event):
        """显示哈希特征示例"""
        await self.container.media_controller.show_dedup_hash_examples(event)

    async def show_dedup_config(self, event):
        """显示去重配置菜单 (与 smart_dedup_settings 同步)"""
        await self.show_smart_dedup_settings(event)

    async def clear_dedup_cache(self, event):
        """清除去重缓存"""
        await self.container.admin_controller.clear_dedup_cache(event)

    # --- 3. Analytics & Performance ---

    async def show_forward_analytics(self, event):
        """显示转发统计详情"""
        await self.container.admin_controller.show_forward_analytics(event)

    async def show_detailed_analytics(self, event):
        """显示详细分析"""
        await self.container.admin_controller.show_detailed_analytics(event)

    async def show_performance_analysis(self, event):
        """显示系统性能分析"""
        await self.container.admin_controller.show_performance_analysis(event)

    async def show_failure_analysis(self, event):
        """显示失败深度分析"""
        await self.container.admin_controller.show_failure_analysis(event)

    async def show_anomaly_detection(self, event):
        """显示异常检测"""
        await self.container.admin_controller.show_anomaly_detection(event)

    async def run_anomaly_detection(self, event):
        """运行异常检测"""
        await self.container.admin_controller.run_anomaly_detection(event)

    async def export_csv_report(self, event):
        """导出 CSV 报告"""
        await self.container.admin_controller.export_csv_report(event)

    async def export_analytics_csv(self, event):
        """导出分析 CSV (别名)"""
        await self.export_csv_report(event)

    async def show_realtime_monitor(self, event):
        """显示系统实时监控"""
        await self.container.admin_controller.show_realtime_monitor(event)

    # --- 4. Rule Management ---

    async def show_rule_list(self, event, page: int = 0, search_query: str = None):
        """显示规则列表 (分页)"""
        await self.container.rule_controller.list_rules(event, page=page, search_query=search_query)

    async def show_rule_detail(self, event, rule_id: int):
        """显示单条规则详情"""
        await self.container.rule_controller.show_detail(event, rule_id)

    async def show_rule_management(self, event, page: int = 0):
        """显示规则管理菜单"""
        await self.show_rule_list(event, page=page)

    async def show_rule_basic_settings(self, event, rule_id: int):
        """显示基础转发设置"""
        await self.container.rule_controller.show_basic_settings(event, rule_id)

    async def show_rule_display_settings(self, event, rule_id: int):
        """显示内容显示设置"""
        await self.container.rule_controller.show_display_settings(event, rule_id)

    async def show_rule_advanced_settings(self, event, rule_id: int):
        """显示高级功能配置"""
        await self.container.rule_controller.show_advanced_settings(event, rule_id)

    async def toggle_rule_status(self, event, rule_id: int, from_page: str = 'detail', page: int = 0):
        """快捷切换规则状态"""
        await self.container.rule_controller.toggle_status(event, rule_id, from_page, page)

    async def toggle_setting(self, event, rule_id: int, key: str):
        """通用规则布尔设置切换"""
        await self.container.rule_controller.toggle_setting(event, rule_id, key)

    async def toggle_rule_setting_new(self, event, rule_id: int, setting_key: str):
        """通用规则布尔设置切换 (别名)"""
        await self.toggle_setting(event, rule_id, setting_key)

    async def delete_rule_confirm(self, event, rule_id: int):
        """删除规则二次确认"""
        await self.container.rule_controller.delete_confirm(event, rule_id)

    async def delete_rule_do(self, event, rule_id: int):
        """执行删除规则"""
        await self.container.rule_controller.delete_do(event, rule_id)

    async def show_manage_keywords(self, event, rule_id: int):
        """管理规则关键词"""
        await self.container.rule_controller.show_keywords(event, rule_id)

    async def enter_add_keyword_state(self, event, rule_id: int):
        """进入添加关键词状态"""
        await self.container.rule_controller.enter_add_keyword_state(event, rule_id)

    async def clear_keywords_confirm(self, event, rule_id: int):
        """清空关键词确认"""
        await self.container.rule_controller.clear_keywords_confirm(event, rule_id)

    async def clear_keywords_do(self, event, rule_id: int):
        """执行清空关键词"""
        await self.container.rule_controller.execute_clear_keywords(event, rule_id)

    async def show_manage_replace_rules(self, event, rule_id: int):
        """管理规则替换规则"""
        await self.container.rule_controller.show_replaces(event, rule_id)

    async def enter_add_replace_state(self, event, rule_id: int):
        """进入添加替换规则状态"""
        await self.container.rule_controller.enter_add_replace_state(event, rule_id)

    async def clear_replaces_confirm(self, event, rule_id: int):
        """清空替换规则确认"""
        await self.container.rule_controller.clear_replaces_confirm(event, rule_id)

    async def clear_replaces_do(self, event, rule_id: int):
        """执行清空替换规则"""
        await self.container.rule_controller.execute_clear_replaces(event, rule_id)

    async def show_rule_statistics(self, event):
        """显示规则统计数据"""
        await self.container.rule_controller.show_rule_statistics(event)

    async def show_rule_status(self, event, rule_id: int):
        """显示具体规则状态页"""
        await self.container.rule_controller.show_rule_status(event, rule_id)

    async def show_sync_config(self, event, rule_id: int):
        """显示同步配置"""
        await self.container.rule_controller.show_sync_config(event, rule_id)

    async def show_multi_source_management(self, event, page: int = 0):
        """显示多源管理中心"""
        await self.container.rule_controller.show_multi_source_management(event, page)

    async def show_multi_source_detail(self, event, rule_id: int):
        """显示多源规则详情"""
        await self.container.rule_controller.show_multi_source_detail(event, rule_id)

    async def show_copy_rule_selection(self, event, rule_id: int, page: int = 0):
        """显示复制规则目标选择"""
        await self.container.rule_controller.show_copy_selection(event, rule_id, page)

    async def perform_rule_copy(self, event, source_id: int, target_id: int):
        """执行规则复制"""
        await self.container.rule_controller.perform_copy(event, source_id, target_id)

    async def show_current_chat_rules(self, event, chat_id: str):
        """显示当前会话的规则列表"""
        await self.container.rule_controller.list_rules(event, search_query=str(chat_id))

    async def show_other_settings(self, event, rule_id: int):
        """显示其他杂项设置"""
        await self.container.rule_controller.show_other_settings(event, rule_id)

    async def handle_ufb_item(self, event, item_type: str):
        """处理 UFB 绑定项切换"""
        await self.container.rule_controller.handle_ufb_item(event, item_type)

    # --- 5. Media & AI Settings ---

    async def show_media_settings(self, event, rule_id: int):
        """显示规则媒体设置"""
        await self.container.media_controller.show_settings(event, rule_id)

    async def show_media_filter_config(self, event):
        """显示全局媒体过滤配置"""
        await self.container.media_controller.show_media_filter_config(event)

    async def toggle_global_media(self, event, media_type: str):
        """切换全局媒体类型拦截"""
        from services.forward_settings_service import forward_settings_service
        await forward_settings_service.toggle_media_type(media_type)
        await self.container.media_controller.show_media_filter_config(event)

    async def show_media_extension_hub(self, event):
        """显示高级扩展名过滤中心"""
        await self.container.media_controller.show_media_extension_hub(event)

    async def toggle_global_extension(self, event, extension: str):
        """切换全局扩展名过滤"""
        await self.container.media_controller.toggle_global_extension(event, extension)

    async def show_max_media_size_selection(self, event, rule_id: int):
        """显示媒体大小限制选择"""
        await self.container.media_controller.show_max_size_selection(event, rule_id)

    async def set_max_media_size(self, event, rule_id: int, size: int):
        """设置最大媒体大小"""
        await self.container.media_controller.set_max_size(event, rule_id, size)

    async def toggle_media_boolean(self, event, rule_id: int, field: str):
        """切换媒体布尔选项"""
        await self.container.media_controller.toggle_boolean(event, rule_id, field)

    async def show_media_types_selection(self, event, rule_id: int):
        """显示媒体类型过滤选择"""
        await self.container.media_controller.show_types_selection(event, rule_id)

    async def toggle_media_type(self, event, rule_id: int, media_type: str):
        """切换特定规则的媒体类型过滤"""
        await self.container.media_controller.toggle_type(event, rule_id, media_type)

    async def show_media_extensions_page(self, event, rule_id: int, page: int = 0):
        """规则扩展名过滤分页页"""
        await self.container.media_controller.show_media_extensions(event, rule_id, page)

    async def toggle_media_extension(self, event, rule_id: int, extension: str, page: int = 0):
        """切换规则扩展名过滤"""
        await self.container.media_controller.toggle_extension(event, rule_id, extension, page)

    async def show_push_settings(self, event, rule_id: int, page: int = 0):
        """显示推送目标设置"""
        await self.container.media_controller.show_push_settings(event, rule_id, page)

    async def toggle_push_boolean(self, event, rule_id: int, field: str):
        """切换推送布尔选项"""
        await self.container.media_controller.toggle_boolean(event, rule_id, field)

    async def show_push_config_details(self, event, config_id: int):
        """推送配置详情"""
        await self.container.media_controller.show_push_config_details(event, config_id)

    async def toggle_push_config_status(self, event, config_id: int):
        """启用/禁用推送配置"""
        await self.container.media_controller.toggle_push_config_status(event, config_id)

    async def toggle_media_send_mode(self, event, config_id: int):
        """切换推送配置中的媒体发送模式"""
        await self.container.media_controller.toggle_media_send_mode(event, config_id)

    async def delete_push_config(self, event, config_id: int):
        """物理删除一个推送配置项"""
        await self.container.media_controller.delete_push_config(event, config_id)

    async def enter_add_push_channel_state(self, event, rule_id: int):
        """进入添加推送频道会话"""
        await self.container.media_controller.enter_add_push_channel_state(event, rule_id)

    async def show_ai_settings(self, event, rule_id: int):
        """规则 AI 处理设置"""
        await self.container.media_controller.show_ai_settings(event, rule_id)

    async def show_summary_time_selection(self, event, rule_id: int, page: int = 0):
        """AI 总结时间窗口选择"""
        await self.container.media_controller.show_summary_time_selection(event, rule_id, page)

    async def select_summary_time(self, event, rule_id: int, time: str):
        """保存总结时间设置"""
        await self.container.media_controller.select_summary_time(event, rule_id, time)

    async def show_model_selection(self, event, rule_id: int, page: int = 0):
        """AI 模型仓库选择页"""
        await self.container.media_controller.show_model_selection(event, rule_id, page)

    async def select_ai_model(self, event, rule_id: int, model: str):
        """应用指定的 AI 模型"""
        await self.container.media_controller.select_ai_model(event, rule_id, model)

    async def show_ai_global_settings(self, event):
        """全局 AI 参数中心"""
        await self.container.media_controller.show_ai_global_settings(event)

    async def show_ai_global_model(self, event):
        """全局 AI 默认模型库"""
        await self.container.media_controller.show_ai_global_model(event)

    async def select_global_ai_model(self, event, model: str):
        """应用全局 AI 模型"""
        await self.container.media_controller.select_global_ai_model(event, model)

    async def show_ai_global_concurrency(self, event):
        """全局 AI 并发控制"""
        await self.container.media_controller.show_ai_global_concurrency(event)

    async def set_global_ai_concurrency(self, event, val: int):
        """持久化全局并发限制"""
        await self.container.media_controller.set_global_ai_concurrency(event, val)

    async def run_summary_now(self, event, rule_id: int):
        """即时触发 AI 总结引擎"""
        await self.container.media_controller.run_summary_now(event, rule_id)

    async def enter_set_ai_prompt_state(self, event, rule_id: int, is_summary: bool = False):
        """自定义 AI 提示词状态"""
        await self.container.media_controller.enter_set_ai_prompt_state(event, rule_id, is_summary)

    async def cancel_ai_state(self, event, rule_id: int):
        """逃逸 AI 设置会话"""
        await self.container.media_controller.cancel_ai_state(event, rule_id)

    # --- 6. Database & System Ops ---

    async def show_db_optimization_center(self, event):
        """显示数据库优化维护中心"""
        await self.container.admin_controller.show_optimization_center(event)

    async def show_db_performance_monitor(self, event):
        """获取并展示数据库性能指标"""
        await self.container.admin_controller.show_performance_monitor(event)

    async def refresh_db_performance(self, event):
        """实时刷新性能监控看板"""
        await self.container.admin_controller.show_performance_monitor(event)

    async def run_db_optimization_check(self, event):
        """触发数据库全量优化自检"""
        await self.container.admin_controller.run_optimization_check(event)

    async def show_db_detailed_report(self, event):
        """生成数据库深度状态报告"""
        await self.container.admin_controller.show_db_detailed_report(event)

    async def show_db_optimization_config(self, event):
        """数据库 PRAGMA 与内核参数调优"""
        await self.container.admin_controller.show_db_optimization_config(event)

    async def show_db_index_analysis(self, event):
        """数据库索引碎片与命中率分析"""
        await self.container.admin_controller.show_db_index_analysis(event)

    async def show_db_cache_management(self, event):
        """去重缓存 (Bloom/Hash) 占用与淘汰策略"""
        await self.container.admin_controller.show_db_cache_management(event)

    async def show_db_optimization_logs(self, event):
        """历史数据库运维记录"""
        await self.container.admin_controller.show_db_optimization_logs(event)

    async def show_db_optimization_advice(self, event):
        """AI/智能驱动的索引优化建议"""
        await self.container.admin_controller.show_db_optimization_advice(event)

    async def show_db_query_analysis(self, event):
        """SQL 慢查询与执行计划分析"""
        await self.container.admin_controller.show_db_query_analysis(event)

    async def show_db_performance_trends(self, event):
        """历史性能趋势曲线分析"""
        await self.container.admin_controller.show_db_performance_trends(event)

    async def show_db_alert_management(self, event):
        """数据库阈值告警管理"""
        await self.container.admin_controller.show_db_alert_management(event)

    async def show_db_archive_center(self, event):
        """数据库冷热分离归档中心"""
        await self.container.admin_controller.show_db_archive_center(event)

    async def run_db_archive_once(self, event):
        """即时手动触发一次归档任务"""
        await self.container.admin_controller.run_archive_once(event)

    async def run_db_archive_force(self, event):
        """忽略温控，强制全量归档"""
        await self.container.admin_controller.run_archive_force(event)

    async def show_db_backup(self, event):
        """数据库备份与恢复管理面板"""
        await self.container.admin_controller.show_backup_management(event)

    async def run_db_reindex(self, event):
        """执行全库 REINDEX (阻塞性)"""
        await self.container.admin_controller.run_reindex(event)

    async def rebuild_bloom_index(self, event):
        """重建布隆过滤器内存镜像"""
        await self.container.admin_controller.rebuild_bloom_index(event)

    async def compact_archive(self, event):
        """物理紧缩归档库，回收磁盘空间"""
        await self.container.admin_controller.compact_archive(event)

    async def show_admin_panel(self, event):
        """管理员超级权限面板"""
        await self.container.admin_controller.show_admin_panel(event)

    async def show_system_logs(self, event):
        """实时滚动查询运行日志"""
        await self.container.admin_controller.show_system_logs(event)

    async def show_cache_cleanup(self, event):
        """文件系统临时文件清理界面"""
        await self.container.admin_controller.show_cache_cleanup(event)

    async def show_session_management(self, event):
        """会话 (Sessions) 连接状态管理"""
        await self.container.admin_controller.show_session_management(event)

    async def toggle_maintenance_mode(self, event):
        """切换系统维护模式"""
        await self.container.admin_controller.toggle_maintenance_mode(event)

    async def show_restart_confirm(self, event):
        """系统重启安全确认"""
        await self.container.admin_controller.show_restart_confirm(event)

    async def execute_restart(self, event):
        """执行主进程优雅重启"""
        await self.container.admin_controller.execute_restart(event)

    # --- 7. History & Task Operations ---

    async def show_history_messages(self, event):
        """历史消息迁移与处理中心"""
        await self.container.media_controller.show_history_hub(event)

    async def show_history_task_selector(self, event):
        """历史批量任务模版选择"""
        await self.container.media_controller.show_history_task_selector(event)

    async def show_history_task_actions(self, event):
        """历史任务生命周期控制菜单"""
        await self.container.media_controller.show_task_actions(event)

    async def show_history_time_range(self, event):
        """任务时间跨度切片设置"""
        await self.container.media_controller.show_time_range(event)

    async def show_history_delay_settings(self, event):
        """批量任务注入速率与延迟设置"""
        await self.container.media_controller.show_history_delay_settings(event)

    async def show_current_history_task(self, event):
        """实时查看当前队列中的历史任务"""
        await self.container.media_controller.show_current_history_task(event)

    async def start_history_task(self, event):
        """提交并启动新历史任务"""
        await self.container.media_controller.start_task(event)

    async def pause_history_task(self, event):
        """暂停队列中的历史任务"""
        await self.container.media_controller.pause_task(event)

    async def resume_history_task(self, event):
        """恢复暂停的任务"""
        await self.container.media_controller.start_task(event)

    async def cancel_history_task(self, event):
        """终止并撤销历史任务"""
        await self.container.media_controller.cancel_task(event)

    async def start_dry_run(self, event):
        """不产生实际转发的行为模拟验证"""
        await self.container.media_controller.start_dry_run(event)

    async def show_quick_stats(self, event):
        """轻量级实时转发统计"""
        await self.container.media_controller.show_quick_stats(event)

    async def toggle_history_dedup(self, event):
        """切换历史迁移过程中的动态去重开关"""
        await self.container.media_controller.toggle_dedup(event)


# 全局单例持有者
menu_controller = MenuController()
