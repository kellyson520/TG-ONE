from telethon import events
from core.logging import get_logger
from core.helpers.auto_delete import reply_and_delete

logger = get_logger(__name__)

# Import handlers from submodules
from handlers.commands.rule_commands import (
    handle_bind_command,
    handle_settings_command,
    handle_switch_command,
    handle_add_command,
    handle_replace_command,
    handle_list_keyword_command,
    handle_list_replace_command,
    handle_remove_command,
    handle_clear_all_command,
    handle_export_keyword_command,
    handle_export_replace_command,
    handle_import_command,
    handle_import_excel_command,
    handle_ufb_bind_command,
    handle_ufb_unbind_command,
    handle_ufb_item_change_command,
    handle_clear_all_keywords_command,
    handle_clear_all_keywords_regex_command,
    handle_clear_all_replace_command,
    handle_copy_keywords_command,
    handle_copy_keywords_regex_command,
    handle_copy_replace_command,
    handle_copy_rule_command,
    handle_remove_all_keyword_command,
    handle_add_all_command,
    handle_replace_all_command,
    handle_delete_rule_command,
    handle_list_rule_command,
    handle_delete_rss_user_command,
    handle_help_command,
    handle_start_command,
    handle_changelog_command
)
from handlers.commands.media_commands import (
    handle_set_duration_command,
    handle_set_resolution_command,
    handle_set_size_command,
    handle_download_command
)
from handlers.commands.system_commands import (
    handle_db_optimize_command,
    handle_db_info_command,
    handle_db_backup_command,
    handle_db_health_command,
    handle_system_status_command,
    handle_logs_command,
    handle_download_logs_command,
    handle_video_cache_stats_command,
    handle_video_cache_clear_command,
    handle_update_command,
    handle_rollback_command
)
from handlers.commands.admin_commands import handle_admin_panel_command
from handlers.commands.stats_commands import (
    handle_forward_stats_command,
    handle_forward_search_command
)
from handlers.commands.dedup_commands import (
    handle_dedup_enable_command,
)
# handle_dedup_scan_command is in system commands but used by dedup wrapper
from handlers.commands.system_commands import handle_dedup_scan_command

from handlers.priority_handler import (
    set_priority_handler,
    queue_status_handler
)

async def _check_permission(event):
    """(可选) 统一权限检查"""
    return True

async def register_handlers(client):
    """注册所有命令处理器"""

    # --- 基础命令 ---
    @client.on(events.NewMessage(pattern="/download"))
    async def download_handler(event):
        await handle_download_command(event, client, event.message.text.split())

    @client.on(events.NewMessage(pattern="/cancel"))
    async def cancel_handler(event):
        from services.session_service import session_manager
        if event.sender_id in session_manager.user_sessions:
            if event.chat_id in session_manager.user_sessions[event.sender_id]:
                session_manager.user_sessions[event.sender_id].pop(event.chat_id)
                if not session_manager.user_sessions[event.sender_id]:
                    session_manager.user_sessions.pop(event.sender_id)
        await reply_and_delete(event, "已退出下载模式。")

    # --- 规则 & 设置 ---
    @client.on(events.NewMessage(pattern=r"^/bind"))
    async def bind_wrapper(event):
        await handle_bind_command(event, client, event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/settings"))
    async def settings_wrapper(event):
        await handle_settings_command(event, "settings", event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/switch"))
    async def switch_wrapper(event):
        await handle_switch_command(event)

    # --- 关键字管理 ---
    @client.on(events.NewMessage(pattern=r"^/add(_regex)?(_all)?\b"))
    async def add_wrapper(event):
        cmd = event.message.text.split()[0][1:]
        if "_all" in cmd:
            await handle_add_all_command(event, cmd, event.message.text.split())
        else:
            await handle_add_command(event, cmd, event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/list_keyword"))
    async def list_kw_wrapper(event):
        await handle_list_keyword_command(event)

    @client.on(events.NewMessage(pattern=r"^/remove(_all)?_keyword(_by_id)?"))
    async def remove_kw_wrapper(event):
        cmd = event.message.text.split()[0][1:]
        if "remove_all_keyword" in cmd:
            await handle_remove_all_keyword_command(event, cmd, event.message.text.split())
        else:
            await handle_remove_command(event, cmd, event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/clear_all_keywords(_regex)?"))
    async def clear_kw_wrapper(event):
        cmd = event.message.text.split()[0][1:]
        if "regex" in cmd:
            await handle_clear_all_keywords_regex_command(event, cmd)
        else:
            await handle_clear_all_keywords_command(event, cmd)
            
    @client.on(events.NewMessage(pattern=r"^/copy_keywords(_regex)?"))
    async def copy_kw_wrapper(event):
        cmd = event.message.text.split()[0][1:]
        if "regex" in cmd:
            await handle_copy_keywords_regex_command(event, cmd)
        else:
            await handle_copy_keywords_command(event, cmd)

    # --- 替换规则 ---
    @client.on(events.NewMessage(pattern=r"^/replace(_all)?\b"))
    async def replace_wrapper(event):
         cmd = event.message.text.split()[0][1:]
         if "_all" in cmd:
             await handle_replace_all_command(event, event.message.text.split())
         else:
             await handle_replace_command(event, event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/list_replace"))
    async def list_replace_wrapper(event):
        await handle_list_replace_command(event)

    @client.on(events.NewMessage(pattern=r"^/remove_replace"))
    async def remove_replace_wrapper(event):
        await handle_remove_command(event, "remove_replace", event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/clear_all_replace"))
    async def clear_replace_wrapper(event):
        await handle_clear_all_replace_command(event, "clear_all_replace")

    @client.on(events.NewMessage(pattern=r"^/copy_replace"))
    async def copy_replace_wrapper(event):
        await handle_copy_replace_command(event, "copy_replace")

    # --- 规则生命周期 ---
    @client.on(events.NewMessage(pattern=r"^/list_rule"))
    async def list_rule_wrapper(event):
        await handle_list_rule_command(event, "list_rule", event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/copy_rule"))
    async def copy_rule_wrapper(event):
        await handle_copy_rule_command(event, "copy_rule")
        
    @client.on(events.NewMessage(pattern=r"^/delete_rule"))
    async def delete_rule_wrapper(event):
        await handle_delete_rule_command(event, "delete_rule", event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/clear_all$"))
    async def clear_all_wrapper(event):
         await handle_clear_all_command(event)

    # --- 导入导出 ---
    @client.on(events.NewMessage(pattern=r"^/export_"))
    async def export_wrapper(event):
        cmd = event.message.text.split()[0][1:]
        if "keyword" in cmd:
            await handle_export_keyword_command(event, cmd)
        elif "replace" in cmd:
            await handle_export_replace_command(event, client)

    @client.on(events.NewMessage(pattern=r"^/import_"))
    async def import_wrapper(event):
        cmd = event.message.text.split()[0][1:]
        if "excel" in cmd:
            await handle_import_excel_command(event)
        else:
            await handle_import_command(event, cmd)

    # --- UFB ---
    @client.on(events.NewMessage(pattern=r"^/ufb_"))
    async def ufb_wrapper(event):
        cmd = event.message.text.split()[0][1:]
        if "bind" in cmd and "unbind" not in cmd:
            await handle_ufb_bind_command(event, cmd)
        elif "unbind" in cmd:
            await handle_ufb_unbind_command(event, cmd)
        elif "item_change" in cmd:
             await handle_ufb_item_change_command(event, cmd)

    # --- 媒体设置 ---
    @client.on(events.NewMessage(pattern=r"^/set_duration"))
    async def set_duration_wrapper(event):
        await handle_set_duration_command(event, event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/set_resolution"))
    async def set_res_wrapper(event):
        await handle_set_resolution_command(event, event.message.text.split())
        
    @client.on(events.NewMessage(pattern=r"^/set_size"))
    async def set_size_wrapper(event):
        await handle_set_size_command(event, event.message.text.split())

    # --- 系统与统计 ---
    @client.on(events.NewMessage(pattern=r"^/logs"))
    async def logs_wrapper(event):
         await handle_logs_command(event, event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/download_logs"))
    async def dl_logs_wrapper(event):
         await handle_download_logs_command(event, event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/db_"))
    async def db_wrapper(event):
        cmd = event.message.text.split()[0][1:]
        if "optimize" in cmd: await handle_db_optimize_command(event)
        elif "info" in cmd: await handle_db_info_command(event)
        elif "backup" in cmd: await handle_db_backup_command(event)
        elif "health" in cmd: await handle_db_health_command(event)

    @client.on(events.NewMessage(pattern=r"^/system_status"))
    async def sys_wrapper(event):
         await handle_system_status_command(event)

    @client.on(events.NewMessage(pattern=r"^/admin"))
    async def admin_wrapper(event):
         await handle_admin_panel_command(event)
         
    @client.on(events.NewMessage(pattern=r"^/video_cache_stats"))
    async def vcs_wrapper(event):
        await handle_video_cache_stats_command(event)
        
    @client.on(events.NewMessage(pattern=r"^/video_cache_clear"))
    async def vcc_wrapper(event):
        await handle_video_cache_clear_command(event, event.message.text.split())

    @client.on(events.NewMessage(pattern=r"^/update"))
    async def update_wrapper(event):
        await handle_update_command(event)

    @client.on(events.NewMessage(pattern=r"^/rollback"))
    async def rollback_wrapper(event):
        await handle_rollback_command(event)

    # --- 统计与去重 ---
    @client.on(events.NewMessage(pattern=r"^/forward_stats"))
    async def fs_wrapper(event):
        await handle_forward_stats_command(event, event.message.text)

    @client.on(events.NewMessage(pattern=r"^/forward_search"))
    async def fsr_wrapper(event):
        await handle_forward_search_command(event, event.message.text)

    @client.on(events.NewMessage(pattern=r"^/dedup"))
    async def dedup_wrapper(event):
        cmd = event.message.text.split()[0][1:]
        if "scan" in cmd:
             await handle_dedup_scan_command(event, event.message.text.split())
        else:
             await handle_dedup_enable_command(event, None)
             
    @client.on(events.NewMessage(pattern=r"^/delete_rss_user"))
    async def del_rss_user_wrapper(event):
        await handle_delete_rss_user_command(event, "delete_rss_user", event.message.text.split())

    # --- 优先级 (QoS) ---
    @client.on(events.NewMessage(pattern=r"^/vip"))
    async def vip_wrapper(event):
        await set_priority_handler(event)

    @client.on(events.NewMessage(pattern=r"^/queue_status"))
    async def queue_status_wrapper(event):
        await queue_status_handler(event)

    # --- 通用 ---
    @client.on(events.NewMessage(pattern=r"^/help"))
    async def help_wrapper(event):
        await handle_help_command(event, "help")
        
    @client.on(events.NewMessage(pattern=r"^/start"))
    async def start_wrapper(event):
        await handle_start_command(event)
        
    @client.on(events.NewMessage(pattern=r"^/changelog"))
    async def cl_wrapper(event):
        await handle_changelog_command(event)

    logger.info("Command handlers registered (Refactored)")
