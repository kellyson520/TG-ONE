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
    """
    [Legacy] 此函数已弃用。
    所有命令现在由 handlers/bot_handler.py 统一分发，
    并由 listeners/message_listener.py 监听。
    """
    logger.info("Legacy command registration skipped (New Architecture active)")


    logger.info("Command handlers registered (Refactored)")
