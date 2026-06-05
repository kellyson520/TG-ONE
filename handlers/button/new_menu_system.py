"""
新的菜单系统 (已重构)
采用组合模式，将大类拆分为多个专门的模块，提高维护性。
"""
import logging
from telethon import Button
from .base import BaseMenu

logger = logging.getLogger(__name__)

class NewMenuSystem(BaseMenu):
    """
    新菜单系统 - 充当主入口和调度中心
    """
    def __init__(self):
        super().__init__()
        # 延迟导入以避免循环依赖
        self._system_menu = None
        self._rules_menu = None
        self._session_menu = None
        self._filter_menu = None
        self._analytics_menu = None
        self._smart_dedup_menu = None
        self._picker_menu = None
        self._history_module = None

    @property
    def system_menu(self):
        if not self._system_menu:
            from .modules.system_menu import system_menu
            self._system_menu = system_menu
        return self._system_menu

    @property
    def rules_menu(self):
        if not self._rules_menu:
            from .modules.rules_menu import rules_menu
            self._rules_menu = rules_menu
        return self._rules_menu

    @property
    def session_menu(self):
        # [Legacy Redirect] 现已迁移至 MediaController 和 SessionRenderer
        return self

    @property
    def filter_menu(self):
        if not self._filter_menu:
            from .modules.filter_menu import filter_menu
            self._filter_menu = filter_menu
        return self._filter_menu

    @property
    def analytics_menu(self):
        if not self._analytics_menu:
            from .modules.analytics_menu import analytics_menu
            self._analytics_menu = analytics_menu
        return self._analytics_menu

    @property
    def smart_dedup_menu(self):
        # [Legacy Redirect] 现已迁移至 menu_controller 和 dedup_renderer
        return self

    @property
    def picker_menu(self):
        if not self._picker_menu:
            from .modules.picker_menu import picker_menu
            self._picker_menu = picker_menu
        return self._picker_menu

    @property
    def history_module(self):
        if not self._history_module:
            from .modules.history import history_module
            self._history_module = history_module
        return self._history_module

    # --- 统一调度方法 ---

    async def show_main_menu(self, event):
        """显示主菜单"""
        from controllers.menu_controller import menu_controller
        await menu_controller.show_main_menu(event)

    async def show_forward_hub(self, event):
        """显示转发管理中心"""
        from controllers.menu_controller import menu_controller
        await menu_controller.show_forward_hub(event)

    async def show_dedup_hub(self, event):
        """显示智能去重中心"""
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_hub(event)

    async def show_analytics_hub(self, event):
        """显示数据分析中心"""
        from controllers.menu_controller import menu_controller
        await menu_controller.show_analytics_hub(event)

    async def show_system_hub(self, event):
        """显示系统设置中心"""
        from controllers.menu_controller import menu_controller
        await menu_controller.show_system_hub(event)

    # --- 模块化功能代理 ---

    # 1. 规则与管理 (Rules)
    async def show_rule_list(self, event, page=1): await self.rules_menu.show_rule_list(event, page)
    async def show_rule_management(self, event, page=0):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_rule_management(event, page)
    async def show_multi_source_management(self, event, page=0): await self.rules_menu.show_multi_source_management(event, page)
    async def show_multi_source_detail(self, event, rule_id): await self.rules_menu.show_multi_source_detail(event, rule_id)
    async def show_rule_selection_for_settings(self, event): await self.rules_menu.show_rule_selection_for_settings(event)
    async def show_rule_status(self, event, rule_id): await self.rules_menu.show_rule_status(event, rule_id)
    async def show_sync_config(self, event, rule_id): await self.rules_menu.show_sync_config(event, rule_id)
    async def show_forward_management(self, event): await self.show_rule_management(event)
    async def show_channel_management_global(self, event): await self.show_rule_management(event)
    async def show_rule_detail_settings(self, event, rule_id):
        from .callback.modules.rule_settings import callback_rule_settings
        message = await event.get_message()
        await callback_rule_settings(event, rule_id, None, message, "")

    # 2. 搜索逻辑
    async def show_forward_search(self, event):
        from .callback.search_callback import handle_search_callback
        await handle_search_callback(event)

    # 3. 筛选设置 (Filter)
    async def show_filter_settings(self, event): await self.filter_menu.show_filter_settings(event)
    async def show_media_types(self, event): await self.filter_menu.show_media_types(event)
    async def show_media_size_settings(self, event): await self.filter_menu.show_media_size_settings(event)
    async def show_media_duration_settings(self, event): await self.filter_menu.show_media_duration_settings(event)
    async def show_media_extension_settings(self, event): await self.filter_menu.show_media_extension_settings(event)

    # 4. 系统管理 (System)
    async def show_system_settings(self, event): await self.system_menu.show_system_settings(event)
    async def show_db_backup(self, event): await self.system_menu.show_db_backup_menu(event)
    async def confirm_backup(self, event): await self.system_menu.confirm_backup(event)
    async def do_backup(self, event): await self.system_menu.do_backup(event)
    async def show_backup_history(self, event, page=0): await self.system_menu.show_backup_history(event, page)
    async def confirm_restore_backup(self, event, backup_index): await self.system_menu.confirm_restore_backup(event, backup_index)
    async def show_system_overview(self, event): await self.system_menu.show_system_overview(event)
    async def confirm_cache_cleanup(self, event): await self.system_menu.confirm_cache_cleanup(event)
    async def do_cache_cleanup(self, event): await self.system_menu.do_cache_cleanup(event)
    async def show_system_status(self, event): await self.system_menu.show_system_status(event)
    async def show_log_viewer(self, event): await self.system_menu.show_log_viewer(event)
    async def show_version_info(self, event): await self.system_menu.show_version_info(event)
    async def do_restore(self, event, index): await self.system_menu.do_restore(event, index)
    async def show_dedup_config(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_config(event)

    # 5. 数据分析 (Analytics)
    async def show_forward_analytics(self, event): await self.analytics_menu.show_forward_analytics(event)
    async def show_detailed_analytics(self, event): await self.analytics_menu.show_detailed_analytics(event)
    async def show_performance_analysis(self, event): await self.analytics_menu.show_performance_analysis(event)
    async def show_failure_analysis(self, event): await self.analytics_menu.show_failure_analysis(event)
    async def export_report(self, event): await self.analytics_menu.export_report(event)
    async def show_anomaly_detection(self, event): await self.analytics_menu.show_anomaly_detection(event)

    # 6. 智能去重 (Smart Dedup - Refactored to Controller)
    async def show_smart_dedup_settings(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_smart_dedup_settings(event)

    async def show_dedup_similarity(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_similarity(event)

    async def show_dedup_content_hash(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_content_hash(event)

    async def show_dedup_video(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_video(event)

    async def show_dedup_time_window(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_time_window(event)

    async def show_dedup_statistics(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_statistics(event)

    async def show_dedup_advanced(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_advanced(event)

    async def show_dedup_sticker(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_sticker(event)

    async def show_dedup_global(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_global(event)

    async def show_dedup_album(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_album(event)

    async def show_dedup_hash_examples(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_dedup_hash_examples(event)
    async def show_dedup_cache_management(self, event):
         await self._render_from_text(event, "🧹 **去重缓存管理**\n\n[开发中] 此处将显示各规则的活跃缓存命中率、过期条数，并支持手动清理特定规则的哈希集。", [[Button.inline("👈 返回", "new_menu:smart_dedup_settings")]])

    # 7. 会话管理 (Session Ops - Refactored to Controller)
    async def show_session_management(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_session_management(event)

    async def show_session_dedup_menu(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.container.media_controller.show_session_dedup_menu(event)

    async def show_dedup_results(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.container.media_controller.show_dedup_results(event)

    async def start_dedup_scan(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.container.media_controller.start_session_scan(event)

    async def confirm_delete_all_duplicates(self, event):
        from telethon import Button
        text = "❓ **危险操作确认**\n\n确定要删除所有发现的重复消息吗？\n此操作不可撤销！"
        buttons = [
            [Button.inline("✅ 确认删除", "new_menu:execute_delete_all")],
            [Button.inline("❌ 取消", "new_menu:dedup_results")],
        ]
        await self._render_from_text(event, text, buttons)

    async def execute_delete_all_duplicates(self, event):
        from controllers.menu_controller import menu_controller
        success, message = await menu_controller.container.session_service.delete_duplicate_messages(event, mode="all")
        if success:
            await event.answer("✅ 删除任务已后台启动")
            await self.show_session_dedup_menu(event)
        else:
            await event.answer(f"❌ 启动失败: {message}", alert=True)

    async def show_select_delete_menu(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.container.media_controller.show_select_delete_menu(event)

    async def toggle_select(self, event, extra_data):
        from controllers.menu_controller import menu_controller
        signature = ":".join(extra_data) if extra_data else ""
        await menu_controller.container.media_controller.toggle_select_signature(event, signature)

    async def execute_batch_delete(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.container.media_controller.execute_batch_delete(event)

    async def show_delete_session_messages_menu(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.container.media_controller.show_delete_session_messages_menu(event)

    async def show_preview_delete(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.container.media_controller.show_delete_preview(event)

    async def confirm_batch_delete(self, event):
        from telethon import Button
        text = "❓ **批量删除确认**\n\n确定要删除当前时间范围内的所有消息吗？\n此操作不可撤销！"
        buttons = [
            [Button.inline("✅ 确认清理", "new_menu:execute_batch_delete")],
            [Button.inline("❌ 取消", "new_menu:delete_session_messages")],
        ]
        await self._render_from_text(event, text, buttons)

    async def show_message_filter_menu(self, event):
        from .modules.filter_menu import filter_menu
        await filter_menu.show_filter_settings(event)

    # 8. 历史消息转发 (History)
    async def show_history_messages(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_history_messages(event)

    async def show_history_task_selector(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_history_task_selector(event)

    async def show_current_history_task(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_current_history_task(event)

    async def show_history_delay_settings(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_history_delay_settings(event)

    async def show_history_time_range(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_history_time_range(event)
    async def show_time_range_selection(self, event): await self.history_module.show_time_range_selection(event)

    # 9. 选择器 (Pickers)
    async def show_time_picker(self, event, time_type): await self.picker_menu.show_time_picker(event, time_type)
    async def show_day_picker(self, event): await self.picker_menu.show_day_picker(event)
    async def show_single_unit_duration_picker(self, event, side, unit, val=None): await self.picker_menu.show_single_unit_duration_picker(event, side, unit, val)
    async def show_session_numeric_picker(self, event, side, field): await self.picker_menu.show_session_numeric_picker(event, side, field)
    async def show_duration_range_picker(self, event, side): await self.picker_menu.show_duration_range_picker(event, side)
    async def show_wheel_date_picker(self, event, side): await self.picker_menu.show_wheel_date_picker(event, side)

    # 10. 全局与高级 (Advanced)
    async def show_db_archive_center(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_db_archive_center(event)

    async def show_media_filter_config(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_media_filter_config(event)

    async def toggle_global_media(self, event, media_type: str):
        from controllers.menu_controller import menu_controller
        await menu_controller.toggle_global_media(event, media_type)

    async def show_media_extension_hub(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_media_extension_hub(event)

    async def toggle_global_extension(self, event, extension: str):
        from controllers.menu_controller import menu_controller
        await menu_controller.toggle_global_extension(event, extension)

    async def show_ai_global_settings(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_ai_global_settings(event)

    async def show_ai_global_model(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_ai_global_model(event)

    async def select_global_ai_model(self, event, model: str):
        from controllers.menu_controller import menu_controller
        await menu_controller.select_global_ai_model(event, model)

    async def show_ai_global_concurrency(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.show_ai_global_concurrency(event)

    async def set_global_ai_concurrency(self, event, val: int):
        from controllers.menu_controller import menu_controller
        await menu_controller.set_global_ai_concurrency(event, val)

    async def run_archive_once(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.run_db_archive_once(event)

    async def run_archive_force(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.run_db_archive_force(event)

    async def rebuild_bloom(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.rebuild_bloom(event)

    async def compact_archive(self, event):
        from controllers.menu_controller import menu_controller
        await menu_controller.compact_archive(event)

new_menu_system = NewMenuSystem()
