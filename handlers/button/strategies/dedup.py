import logging
from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry

logger = logging.getLogger(__name__)

@MenuHandlerRegistry.register
class DedupMenuStrategy(BaseMenuHandler):
    """
    Handles Deduplication and Session Management actions.
    Purified to delegate all logic to MenuController or relevant systems.
    """

    ACTIONS = {
        "session_management", "history_messages",
        "session_dedup", "dedup_config",
        "start_dedup_scan", "start_dedup_scan_optimized",
        "dedup_results",
        "delete_all_duplicates", "execute_delete_all",
        "dedup_settings", "update_rule_dedup", "reset_rule_dedup",
        "keep_all_duplicates",
        "select_delete_duplicates", "delete_selected_duplicates",
        "delete_session_messages",
        "start_delete_messages", "pause_delete", "stop_delete",
        "preview_delete", "preview_delete_refresh", "confirm_delete",
        # Legacy Rule-Based Dedup
        "dedup_scan_now", "delete_duplicates", "confirm_delete_duplicates",
        "view_source_messages", "keep_duplicates", "toggle_allow_delete_source_on_dedup",
        # Smart Dedup Center (V4)
        "smart_dedup_settings", "dedup_time_window", "dedup_similarity",
        "dedup_content_hash", "dedup_video", "dedup_sticker",
        "dedup_global", "dedup_statistics", "dedup_advanced",
        "dedup_cache_management", "dedup_hash_examples", "dedup_album",
        "toggle_similarity", "set_similarity", "toggle_content_hash",
        "toggle_video_file_id", "toggle_video_partial",
        "toggle_time_window", "set_time_window", "manual_cleanup",
        "reset_dedup_config", "toggle_sticker_filter", "toggle_sticker_strict",
        "toggle_global_search", "toggle_album_dedup", "set_album_threshold",
        "dedup_clear_cache"
    }

    async def match(self, action: str, **kwargs) -> bool:
        if action in self.ACTIONS:
            return True
        if action.startswith("toggle_select"):
            return True
        return False

    async def handle(self, event, action: str, **kwargs):
        from controllers.menu_controller import menu_controller
        from handlers.button.new_menu_system import new_menu_system
        from services.session_service import session_manager

        extra_data = kwargs.get("extra_data", [])
        
        # rule_id extraction
        rule_id = int(extra_data[0]) if extra_data and extra_data[0].isdigit() else 0

        # Mapping actions to controller or system calls
        if action == "session_management":
            await menu_controller.show_session_management(event)
        
        elif action == "history_messages":
            await menu_controller.show_history_messages(event)
        
        elif action == "delete_session_messages":
            await new_menu_system.show_delete_session_messages_menu(event)

        elif action == "session_dedup":
            await new_menu_system.show_session_dedup_menu(event)
        
        elif action == "dedup_config":
            await new_menu_system.show_dedup_config(event)
        
        elif action in ["start_dedup_scan", "start_dedup_scan_optimized"]:
            await new_menu_system.start_dedup_scan(event)

        elif action == "dedup_results":
            await new_menu_system.show_dedup_results(event)
        
        elif action == "delete_all_duplicates":
            await new_menu_system.confirm_delete_all_duplicates(event)
        
        elif action == "execute_delete_all":
            await new_menu_system.execute_delete_all_duplicates(event)
        
        elif action == "keep_all_duplicates":
             # Still logic heavy, but no direct session management here
            success, msg = await session_manager.delete_duplicate_messages(event, mode="keep")
            if success:
                await event.answer("✅ 已保留所有重复项")
                await new_menu_system.show_session_dedup_menu(event)
            else:
                await event.answer(f"❌ 操作失败: {msg}")

        elif action == "select_delete_duplicates":
            await new_menu_system.show_select_delete_menu(event)
        
        elif action.startswith("toggle_select"):
            await new_menu_system.toggle_select(event, extra_data)
        
        elif action == "delete_selected_duplicates":
            success, msg = await session_manager.delete_duplicate_messages(event, mode="select")
            if success:
                await event.answer("✅ 已删除选中重复项")
                await new_menu_system.show_session_dedup_menu(event)
            else:
                await event.answer(f"❌ 删除失败: {msg}")

        elif action == "dedup_settings":
            await menu_controller.show_rule_dedup_settings(event, rule_id)

        elif action == "update_rule_dedup":
            if len(extra_data) >= 3:
                await menu_controller.update_rule_dedup(event, rule_id, extra_data[1], extra_data[2])
            else: await event.answer("参数错误")

        elif action == "reset_rule_dedup":
             await menu_controller.reset_rule_dedup(event, rule_id)

        elif action == "start_delete_messages":
            success, msg = await session_manager.delete_session_messages_by_filter(event)
            if success:
                await event.answer("✅ 开始删除消息")
                await new_menu_system.show_delete_session_messages_menu(event)
            else:
                await event.answer(f"❌ 启动失败: {msg}")
        
        elif action in ["pause_delete", "stop_delete"]:
             method = session_manager.pause_delete_task if action == "pause_delete" else session_manager.stop_delete_task
             if await method(event.chat_id):
                 await event.answer(f"✅ 任务{'暂停' if action == 'pause_delete' else '停止'}成功")
             else: await event.answer("❌ 操作失败")

        elif action in ["preview_delete", "preview_delete_refresh"]:
            await new_menu_system.show_preview_delete(event)

        elif action == "confirm_delete":
             await new_menu_system.confirm_batch_delete(event)
        
        elif action == "execute_batch_delete":
            await new_menu_system.execute_batch_delete(event)

        # Legacy Rule-Based Dedup mapping to controller
        elif action == "dedup_scan_now":
            await menu_controller.run_legacy_dedup_cmd(event, rule_id, "scan")
        elif action == "delete_duplicates":
            await menu_controller.run_legacy_dedup_cmd(event, rule_id, "delete")
        elif action == "confirm_delete_duplicates":
            await menu_controller.run_legacy_dedup_cmd(event, rule_id, "confirm")
        elif action == "view_source_messages":
            await menu_controller.run_legacy_dedup_cmd(event, rule_id, "view")
        elif action == "keep_duplicates":
            await menu_controller.run_legacy_dedup_cmd(event, rule_id, "keep")
        elif action == "toggle_allow_delete_source_on_dedup":
            await menu_controller.run_legacy_dedup_cmd(event, rule_id, "toggle")

        # Smart Dedup Center Actions
        elif action == "smart_dedup_settings":
            await new_menu_system.show_smart_dedup_settings(event)
        
        elif action == "dedup_time_window":
            await new_menu_system.show_dedup_time_window(event)
        
        elif action == "dedup_similarity":
            await new_menu_system.show_dedup_similarity(event)
        
        elif action == "dedup_content_hash":
            await new_menu_system.show_dedup_content_hash(event)
            
        elif action == "dedup_video":
            await new_menu_system.show_dedup_video(event)
            
        elif action == "dedup_sticker":
            await new_menu_system.show_dedup_sticker(event)
            
        elif action == "dedup_global":
            await new_menu_system.show_dedup_global(event)
            
        elif action == "dedup_advanced":
            await new_menu_system.show_dedup_advanced(event)
            
        elif action == "dedup_statistics":
            await new_menu_system.show_dedup_statistics(event)
            
        elif action == "dedup_hash_examples":
            await new_menu_system.show_dedup_hash_examples(event)
            
        elif action == "dedup_album":
            await new_menu_system.show_dedup_album(event)

        elif action == "dedup_cache_management":
            await new_menu_system.show_dedup_cache_management(event)

        elif action == "dedup_clear_cache":
            await menu_controller.clear_dedup_cache(event)

        # Config Update Actions
        elif action.startswith("toggle_") or action.startswith("set_") or action in ["manual_cleanup", "reset_dedup_config"]:
            # 统一交由服务层处理逻辑
            success, msg = await container.dedup_service.dispatch_config_update(action, extra_data)
            await event.answer(msg, alert=not success)
            
            # 刷新当前页面逻辑
            if success:
                # 确定刷新的页面
                refresh_action = action.split('_')[-1] if '_' in action else action
                if "similarity" in action: await menu_controller.show_dedup_similarity(event)
                elif "content_hash" in action: await menu_controller.show_dedup_content_hash(event)
                elif "video" in action: await menu_controller.show_dedup_video(event)
                elif "time_window" in action: await menu_controller.show_dedup_time_window(event)
                elif "sticker" in action: await menu_controller.show_dedup_sticker(event)
                elif "global" in action: await menu_controller.show_dedup_global(event)
                elif "album" in action: await menu_controller.show_dedup_album(event)
                elif "advanced" in action: await menu_controller.show_dedup_advanced(event)
                elif action == "manual_cleanup": await menu_controller.show_dedup_advanced(event)
                elif action == "reset_dedup_config": await menu_controller.show_smart_dedup_settings(event)
                else: await menu_controller.show_smart_dedup_settings(event)

        else:
            logger.warning(f"DedupStrategy: No handler for action {action}")
