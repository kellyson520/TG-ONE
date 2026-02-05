import traceback
import logging
from services.network.router import RadixRouter

# 导入模块化处理函数
from handlers.button.callback.modules.rule_nav import (
    callback_switch,
    callback_page,
    callback_toggle_current,
    callback_page_rule
)
from handlers.button.callback.modules.rule_settings import (
    callback_settings,
    callback_rule_settings,
    callback_set_delay_time,
    callback_delay_time_page,
    callback_select_delay_time,
)
from handlers.button.callback.modules.rule_actions import callback_delete
from handlers.button.callback.modules.sync_settings import (
    callback_set_sync_rule,
    callback_toggle_rule_sync,
    callback_sync_rule_page
)
from handlers.button.callback.modules.common_utils import (
    callback_close_settings,
    callback_noop
)

# 导入管理面板回调
from .admin_callback import (
    callback_admin_cleanup,
    callback_admin_cleanup_menu,
    callback_admin_cleanup_temp,
    callback_admin_config,
    callback_admin_db_backup,
    callback_admin_db_health,
    callback_admin_db_info,
    callback_admin_db_optimize,
    callback_admin_logs,
    callback_admin_panel,
    callback_admin_restart,
    callback_admin_restart_confirm,
    callback_admin_stats,
    callback_admin_system_status,
    callback_close_admin_panel,
)

# 导入高级媒体设置回调
from .advanced_media_callback import (
    callback_cancel_set_duration_range,
    callback_cancel_set_file_size_range,
    callback_cancel_set_resolution_range,
    callback_set_duration_range,
    callback_set_file_size_range,
    callback_set_resolution_range,
    callback_toggle_duration_filter,
    callback_toggle_file_size_range_filter,
    callback_toggle_resolution_filter,
    handle_advanced_media_callback,
)

# 导入AI设置回调
from .ai_callback import callback_set_summary_time
from .ai_callback import (
    callback_ai_settings,
    callback_cancel_set_prompt,
    callback_cancel_set_summary,
    callback_change_model,
    callback_model_page,
    callback_select_model,
    callback_select_time,
    callback_set_ai_prompt,
    callback_set_summary_prompt,
    callback_summary_now,
    callback_time_page,
    handle_ai_callback,
)

# 导入媒体设置回调
from .media_callback import (
    callback_media_extensions_page,
    callback_media_settings,
    callback_select_max_media_size,
    callback_set_max_media_size,
    callback_set_media_extensions,
    callback_set_media_types,
    callback_toggle_media_allow_text,
    callback_toggle_media_extension,
    callback_toggle_media_type,
    handle_media_callback,
)
from .new_menu_callback import handle_new_menu_callback

# 导入其他通用设置回调
from .other_callback import (
    callback_cancel_set_original_link,
    callback_cancel_set_time,
    callback_cancel_set_userinfo,
    callback_clear_keyword,
    callback_clear_replace,
    callback_confirm_delete_duplicates,
    callback_copy_keyword,
    callback_copy_replace,
    callback_copy_rule,
    callback_dedup_scan_now,
    callback_delete_duplicates,
    callback_delete_rule,
    callback_keep_duplicates,
    callback_other_settings,
    callback_perform_clear_keyword,
    callback_perform_clear_replace,
    callback_perform_copy_keyword,
    callback_perform_copy_replace,
    callback_perform_copy_rule,
    callback_perform_delete_rule,
    callback_set_original_link_template,
    callback_set_time_template,
    callback_set_userinfo_template,
    callback_toggle_allow_delete_source_on_dedup,
    callback_toggle_reverse_blacklist,
    callback_toggle_reverse_whitelist,
    callback_view_source_messages,
    handle_other_callback,
)

# 导入推送设置回调
from .push_callback import (
    callback_add_push_channel,
    callback_cancel_add_push_channel,
    callback_delete_push_config,
    callback_push_page,
    callback_push_settings,
    callback_toggle_enable_only_push,
    callback_toggle_enable_push,
    callback_toggle_media_send_mode,
    callback_toggle_push_config,
    callback_toggle_push_config_status,
)
from .search_callback import handle_search_callback

logger = logging.getLogger(__name__)

# 回调处理器字典
CALLBACK_HANDLERS = {
    "toggle_current": callback_toggle_current,
    "switch": callback_switch,
    "settings": callback_settings,
    "delete": callback_delete,
    "page": callback_page,
    "rule_settings": callback_rule_settings,
    "set_summary_time": callback_set_summary_time,
    "set_delay_time": callback_set_delay_time,
    "select_delay_time": callback_select_delay_time,
    "delay_time_page": callback_delay_time_page,
    "page_rule": callback_page_rule,
    "close_settings": callback_close_settings,
    "set_sync_rule": callback_set_sync_rule,
    "toggle_rule_sync": callback_toggle_rule_sync,
    "sync_rule_page": callback_sync_rule_page,
    # AI设置
    "set_summary_prompt": callback_set_summary_prompt,
    "set_ai_prompt": callback_set_ai_prompt,
    "ai_settings": callback_ai_settings,
    "time_page": callback_time_page,
    "select_time": callback_select_time,
    "select_model": callback_select_model,
    "model_page": callback_model_page,
    "change_model": callback_change_model,
    "cancel_set_prompt": callback_cancel_set_prompt,
    "cancel_set_summary": callback_cancel_set_summary,
    "summary_now": callback_summary_now,
    # 媒体设置
    "select_max_media_size": callback_select_max_media_size,
    "set_max_media_size": callback_set_max_media_size,
    "media_settings": callback_media_settings,
    "set_media_types": callback_set_media_types,
    "toggle_media_type": callback_toggle_media_type,
    "set_media_extensions": callback_set_media_extensions,
    "media_extensions_page": callback_media_extensions_page,
    "toggle_media_extension": callback_toggle_media_extension,
    "toggle_media_allow_text": callback_toggle_media_allow_text,
    "noop": callback_noop,
    # 其他设置
    "other_settings": callback_other_settings,
    "copy_rule": callback_copy_rule,
    "copy_keyword": callback_copy_keyword,
    "copy_replace": callback_copy_replace,
    "clear_keyword": callback_clear_keyword,
    "clear_replace": callback_clear_replace,
    "delete_rule": callback_delete_rule,
    "perform_copy_rule": callback_perform_copy_rule,
    "perform_copy_keyword": callback_perform_copy_keyword,
    "perform_copy_replace": callback_perform_copy_replace,
    "perform_clear_keyword": callback_perform_clear_keyword,
    "perform_clear_replace": callback_perform_clear_replace,
    "perform_delete_rule": callback_perform_delete_rule,
    "set_userinfo_template": callback_set_userinfo_template,
    "set_time_template": callback_set_time_template,
    "set_original_link_template": callback_set_original_link_template,
    "cancel_set_userinfo": callback_cancel_set_userinfo,
    "cancel_set_time": callback_cancel_set_time,
    "cancel_set_original_link": callback_cancel_set_original_link,
    "toggle_reverse_blacklist": callback_toggle_reverse_blacklist,
    "toggle_reverse_whitelist": callback_toggle_reverse_whitelist,
    "dedup_scan_now": callback_dedup_scan_now,
    # 推送设置
    "push_settings": callback_push_settings,
    "toggle_enable_push": callback_toggle_enable_push,
    "toggle_enable_only_push": callback_toggle_enable_only_push,
    "add_push_channel": callback_add_push_channel,
    "cancel_add_push_channel": callback_cancel_add_push_channel,
    "toggle_push_config": callback_toggle_push_config,
    "toggle_push_config_status": callback_toggle_push_config_status,
    "toggle_media_send_mode": callback_toggle_media_send_mode,
    "delete_push_config": callback_delete_push_config,
    "push_page": callback_push_page,
    # 管理面板回调
    "admin_db_info": callback_admin_db_info,
    "admin_db_health": callback_admin_db_health,
    "admin_db_backup": callback_admin_db_backup,
    "admin_db_optimize": callback_admin_db_optimize,
    "admin_system_status": callback_admin_system_status,
    "admin_logs": callback_admin_logs,
    "admin_cleanup_menu": callback_admin_cleanup_menu,
    "admin_cleanup": callback_admin_cleanup,
    "admin_cleanup_temp": callback_admin_cleanup_temp,
    "admin_vacuum_db": callback_admin_db_optimize,
    "admin_analyze_db": callback_admin_db_optimize,
    "admin_full_optimize": callback_admin_db_optimize,
    "admin_stats": callback_admin_stats,
    "admin_config": callback_admin_config,
    "admin_restart": callback_admin_restart,
    "admin_restart_confirm": callback_admin_restart_confirm,
    "admin_panel": callback_admin_panel,
    "close_admin_panel": callback_close_admin_panel,
    # 高级媒体筛选回调
    "toggle_duration_filter": callback_toggle_duration_filter,
    "set_duration_range": callback_set_duration_range,
    "cancel_set_duration_range": callback_cancel_set_duration_range,
    "toggle_resolution_filter": callback_toggle_resolution_filter,
    "set_resolution_range": callback_set_resolution_range,
    "cancel_set_resolution_range": callback_cancel_set_resolution_range,
    "toggle_file_size_range_filter": callback_toggle_file_size_range_filter,
    "set_file_size_range": callback_set_file_size_range,
    "cancel_set_file_size_range": callback_cancel_set_file_size_range,
    # 去重按钮回调
    "delete_duplicates": callback_delete_duplicates,
    "view_source_messages": callback_view_source_messages,
    "keep_duplicates": callback_keep_duplicates,
    "confirm_delete_duplicates": callback_confirm_delete_duplicates,
    "toggle_allow_delete_source_on_dedup": callback_toggle_allow_delete_source_on_dedup,
}

# 初始化全局路由器
callback_router = RadixRouter()
callback_router.build_from_dict(CALLBACK_HANDLERS)

# 添加带参数的高级路由支持
callback_router.add_route("rule:{id}:settings", callback_rule_settings)
callback_router.add_route("rule_settings:{id}", callback_rule_settings)
callback_router.add_route("delete:{id}", callback_delete)
callback_router.add_route("switch:{id}", callback_switch)

# [Phase 3 Extension] 整合通配路由
callback_router.add_route("new_menu:{rest}", handle_new_menu_callback)
callback_router.add_route("search:{rest}", handle_search_callback)
callback_router.add_route("media_settings:{rest}", handle_media_callback)
callback_router.add_route("set_max_media_size:{rest}", handle_media_callback)
callback_router.add_route("select_max_media_size:{rest}", handle_media_callback)
callback_router.add_route("set_media_types:{rest}", handle_media_callback)
callback_router.add_route("toggle_media_type:{rest}", handle_media_callback)
callback_router.add_route("set_media_extensions:{rest}", handle_media_callback)
callback_router.add_route("media_extensions_page:{rest}", handle_media_callback)
callback_router.add_route("toggle_media_extension:{rest}", handle_media_callback)
callback_router.add_route("toggle_media_allow_text:{rest}", handle_media_callback)
callback_router.add_route("open_duration_picker:{rest}", handle_advanced_media_callback)
callback_router.add_route("ai_settings:{rest}", handle_ai_callback)
callback_router.add_route("set_summary_time:{rest}", handle_ai_callback)
callback_router.add_route("other_callback:{rest}", handle_other_callback)

# 更新日志翻页
from handlers.button.callback.modules.changelog_callback import callback_changelog_page
callback_router.add_route("cl_page:{page}", callback_changelog_page)

# 确认更新
from handlers.commands.system_commands import callback_confirm_update
callback_router.add_route("confirm_update", callback_confirm_update)

# [Fix] 通用 Toggle 处理器 - 处理所有 toggle_* 回调
from .generic_toggle import handle_generic_toggle

# 注册所有缺失的 toggle 路由
# 规则基础设置
callback_router.add_route("toggle_enable_rule:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_add_mode:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_filter_user_info:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_forward_mode:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_bot:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_replace:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_message_mode:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_preview:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_original_link:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_delete_original:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_ufb:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_original_sender:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_original_time:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_enable_delay:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_handle_mode:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_enable_comment_button:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_only_rss:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_force_pure_forward:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_enable_dedup:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_enable_sync:{rest}", handle_generic_toggle)

# AI 设置
callback_router.add_route("toggle_ai:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_ai_upload_image:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_keyword_after_ai:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_summary:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_top_summary:{rest}", handle_generic_toggle)

# 媒体设置
callback_router.add_route("toggle_enable_media_type_filter:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_enable_media_size_filter:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_enable_media_extension_filter:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_media_extension_filter_mode:{rest}", handle_generic_toggle)
callback_router.add_route("toggle_send_over_media_size_message:{rest}", handle_generic_toggle)


async def handle_callback(event):
    """处理所有回调查询 (基于 RadixRouter)"""
    try:
        data = event.data.decode("utf-8")
        logger.debug(f"Router分派: {data}")

        if data.startswith("new_menu:"):
            await handle_new_menu_callback(event)
            return

        match_result = callback_router.match(data)
        handler, params = match_result
        
        if handler is None:
            logger.warning(f"路由匹配失败 (处理器为空): {data}")
            await event.answer("操作已过期或指令无效", alert=True)
            return
        
        event.router_params = params
            
        # [Fix] 兼容 5 参数的旧版模块化处理器
        import inspect
        sig = inspect.signature(handler)
        if len(sig.parameters) == 5:
            # 提取参数
            rule_id = params.get('id') or params.get('rule_id')
            if not rule_id and ":" in data:
                parts = data.split(":")
                if len(parts) > 1 and parts[1].isdigit():
                    rule_id = parts[1]
            
            # [Fix] 校验 rule_id
            if not rule_id:
                logger.warning(f"回调数据缺失 rule_id: {data}")
                await event.answer("无效的指令参数", alert=True)
                return

            # 构造上下文 (session 传 None 由处理器内部创建，data 传原始字符串)
            message = await event.get_message()
            return await handler(event, rule_id, None, message, data)

        # 正常分发
        if params:
            return await handler(event, **params)
        return await handler(event)

    except Exception as e:
        import traceback
        logger.error(f"回调处理异常: {e}\n{traceback.format_exc()}")
        try:
            await event.answer("操作处理出错，请重试", alert=True)
        except Exception:
            pass
