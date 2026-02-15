import traceback
import logging
from core.container import container
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
from .admin_callback import handle_admin_callback

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
from .ai_callback import callback_set_summary_time  # Still used in dict? No, replaced.
from .ai_callback import handle_ai_callback

# 导入媒体设置回调
from .media_callback import handle_media_callback
from .menu_entrypoint import handle_new_menu_callback

# 导入其他通用设置回调
from .other_callback import (
    handle_other_callback,
    # These legacy ones are still needed for fallback in handle_other_callback
    # BUT handle_other_callback imports them internally.
    # callback_handlers.py dict NO LONGER uses them directly (it uses handle_other_callback)
    # So we can remove them IF we are sure handle_other_callback imports them from modules.
    # handle_other_callback imports from .callback_handlers import callback_toggle_current ...
    # This means callback_handlers MUST export them!
)
# Re-exporting legacy handlers for handle_other_callback
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
# We need to re-export imports that handle_other_callback uses from here?
# handle_other_callback imports:
# callback_toggle_current, callback_switch, callback_settings,
# callback_delete, callback_page, callback_rule_settings,
# callback_set_delay_time, callback_select_delay_time,
# callback_delay_time_page, callback_page_rule, callback_close_settings,
# callback_set_sync_rule, callback_toggle_rule_sync, callback_sync_rule_page,
# callback_set_summary_time, callback_handle_ufb_item

# callback_set_summary_time was in ai_callback.
# handle_other_callback imports it from .callback_handlers.
# So we MUST import it here from ai_callback.
from .ai_callback import callback_set_summary_time

# callback_handle_ufb_item was in other_callback itself.
# handle_other_callback imports it from .callback_handlers?
# Let's check other_callback again.
# handle_other_callback imports callback_handle_ufb_item from .callback_handlers.
# BUT callback_handlers.py did NOT import it in the original code snippet (Step 492).
# Line 126 was handle_other_callback.
# Line 116 was ufb_item mapping to callback_handle_ufb_item.
# But where was callback_handle_ufb_item imported from?
# It wasn't in the import list of Step 492!
# Ah, it was probably defined in other_callback.py and NOT imported in callback_handlers.py?
# Line 116 in other_callback.py says: "ufb_item": callback_handle_ufb_item
# And callback_handle_ufb_item is defined in other_callback.py at line 449.
# So handle_other_callback uses it directly from module scope.
# BUT `from .callback_handlers import ... callback_handle_ufb_item` in Step 496 Line 69?
# This implies callback_handlers.py EXPORTS it.
# If Step 492 didn't show it, maybe I missed it or it was implicit?
# Wait, Step 492 shows `callback_handlers.py` FULL file.
# I search "callback_handle_ufb_item".
# It is NOT imported.
# But it IS used in the dict? Line 116?
# Ah, Line 116 in `other_callback.py` uses it.
# Line 254 in `callback_handlers.py` (Step 502) has "ufb_item": handle_other_callback.
# In Step 492 (Original), Line 116 was NOT in CALLBACK_HANDLERS?
# Line 254 in Step 492 was `}`.
# I don't see `ufb_item` in Step 492 `CALLBACK_HANDLERS`.
# I see `callback_handle_ufb_item` nowhere in Step 492.
# So `other_callback.py` lines 63-70 import `callback_handle_ufb_item` from `callback_handlers`?
# If `callback_handlers` doesn't have it, `other_callback` would crash with ImportError.
# This suggests `other_callback.py` code I saw in Step 496 might be relying on something I can't see or it was broken?
# OR `callback_handle_ufb_item` is defined in `other_callback.py` and used there.
# But Line 69 `callback_handle_ufb_item` in import block suggests it expects it from callback_handlers.
# This is confusing.

# Recommendation: In `other_callback.py`, `callback_handle_ufb_item` is DEFINED in `other_callback.py` (Line 449).
# So `handle_other_callback` (Line 41) can just use it directly.
# The import `from .callback_handlers import ...` is likely for OTHER handlers.
# If `callback_handle_ufb_item` is in that import list, then `callback_handlers` MUST export it.
# Since `callback_handlers` (Step 492) does NOT seem to export it, `other_callback.py` code involving that import might be wrong or legacy.
# However, `handle_other_callback` uses the dict.
# If I look at `other_callback.py` again (Step 496):
# Line 116: "ufb_item": callback_handle_ufb_item.
# This `callback_handle_ufb_item` refers to the function defined in the same file (Line 449).
# It does NOT refer to the imported one (unless shadowed).
# So the import in Line 69 might be redundant or error-prone.
# I should remove `callback_handle_ufb_item` from the import list in `other_callback.py` if I can.
# But I am editing `callback_handlers.py`.

# I will assume `callback_handlers.py` does NOT need to export `callback_handle_ufb_item`.

# 导入推送设置回调
from .push_callback import handle_push_callback
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
    "set_summary_time": handle_ai_callback, # Redirect to AI
    "set_delay_time": callback_set_delay_time,
    "select_delay_time": callback_select_delay_time,
    "delay_time_page": callback_delay_time_page,
    "page_rule": callback_page_rule,
    "close_settings": callback_close_settings,
    "set_sync_rule": callback_set_sync_rule,
    "toggle_rule_sync": callback_toggle_rule_sync,
    "sync_rule_page": callback_sync_rule_page,
    
    # AI设置 -> Redirect to handle_ai_callback
    "set_summary_prompt": handle_ai_callback,
    "set_ai_prompt": handle_ai_callback,
    "ai_settings": handle_ai_callback,
    "time_page": handle_ai_callback,
    "select_time": handle_ai_callback,
    "select_model": handle_ai_callback,
    "model_page": handle_ai_callback,
    "change_model": handle_ai_callback,
    "cancel_set_prompt": handle_ai_callback,
    "cancel_set_summary": handle_ai_callback,
    "summary_now": handle_ai_callback,
    
    # 媒体设置 -> Redirect to handle_media_callback
    "select_max_media_size": handle_media_callback,
    "set_max_media_size": handle_media_callback,
    "media_settings": handle_media_callback,
    "set_media_types": handle_media_callback,
    "toggle_media_type": handle_media_callback,
    "set_media_extensions": handle_media_callback,
    "media_extensions_page": handle_media_callback,
    "toggle_media_extension": handle_media_callback,
    "toggle_media_allow_text": handle_media_callback,
    "noop": callback_noop,
    
    # 其他设置 -> Redirect to handle_other_callback (migrated ones)
    "other_settings": handle_other_callback,
    "copy_rule": handle_other_callback,
    "copy_keyword": handle_other_callback,
    "copy_replace": handle_other_callback,
    "clear_keyword": handle_other_callback,
    "clear_replace": handle_other_callback,
    "delete_rule": handle_other_callback,
    "perform_copy_rule": handle_other_callback,
    "perform_copy_keyword": handle_other_callback,
    "perform_copy_replace": handle_other_callback,
    "perform_clear_keyword": handle_other_callback,
    "perform_clear_replace": handle_other_callback,
    "perform_delete_rule": handle_other_callback,
    "dedup_scan_now": handle_other_callback,
    "delete_duplicates": handle_other_callback,
    "view_source_messages": handle_other_callback,
    "keep_duplicates": handle_other_callback,
    "confirm_delete_duplicates": handle_other_callback,
    "toggle_allow_delete_source_on_dedup": handle_other_callback,
    "ufb_item": handle_other_callback,

    # Legacy/Not yet fully migrated to Strategy Registry but handled by other_callback fallback?
    # Note: common_utils like set_userinfo_template are still in other_callback fallback or handled by Other
    "set_userinfo_template": handle_other_callback,
    "set_time_template": handle_other_callback,
    "set_original_link_template": handle_other_callback,
    "cancel_set_userinfo": handle_other_callback,
    "cancel_set_time": handle_other_callback,
    "cancel_set_original_link": handle_other_callback,
    "toggle_reverse_blacklist": handle_other_callback,
    "toggle_reverse_whitelist": handle_other_callback,
    
    # 推送设置 -> Redirect to handle_push_callback
    "push_settings": handle_push_callback,
    "toggle_enable_push": handle_push_callback,
    "toggle_enable_only_push": handle_push_callback,
    "add_push_channel": handle_push_callback,
    "cancel_add_push_channel": handle_push_callback,
    "toggle_push_config": handle_push_callback,
    "toggle_push_config_status": handle_push_callback,
    "toggle_media_send_mode": handle_push_callback,
    "delete_push_config": handle_push_callback,
    "push_page": handle_push_callback,
    
    # 管理面板回调 -> Redirect to handle_admin_callback
    "admin_db_info": handle_admin_callback,
    "admin_db_health": handle_admin_callback,
    "admin_db_backup": handle_admin_callback,
    "admin_db_optimize": handle_admin_callback,
    "admin_system_status": handle_admin_callback,
    "admin_logs": handle_admin_callback,
    "admin_cleanup_menu": handle_admin_callback,
    "admin_cleanup": handle_admin_callback,
    "admin_cleanup_temp": handle_admin_callback,
    "admin_vacuum_db": handle_admin_callback,
    "admin_analyze_db": handle_admin_callback,
    "admin_full_optimize": handle_admin_callback,
    "admin_stats": handle_admin_callback,
    "admin_config": handle_admin_callback,
    "admin_restart": handle_admin_callback,
    "admin_restart_confirm": handle_admin_callback,
    "admin_panel": handle_admin_callback,
    "close_admin_panel": handle_admin_callback,
    
    # 高级媒体筛选回调 -> Handled by AdvancedMedia (not yet migrated to generic strategy?)
    # or handle_advanced_media_callback
    "toggle_duration_filter": callback_toggle_duration_filter,
    "set_duration_range": callback_set_duration_range,
    "cancel_set_duration_range": callback_cancel_set_duration_range,
    "toggle_resolution_filter": callback_toggle_resolution_filter,
    "set_resolution_range": callback_set_resolution_range,
    "cancel_set_resolution_range": callback_cancel_set_resolution_range,
    "toggle_file_size_range_filter": callback_toggle_file_size_range_filter,
    "set_file_size_range": callback_set_file_size_range,
    "cancel_set_file_size_range": callback_cancel_set_file_size_range,
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
# [Fix] 补全 AI 设置相关路由
callback_router.add_route("set_summary_prompt:{rest}", handle_ai_callback)
callback_router.add_route("set_ai_prompt:{rest}", handle_ai_callback)
callback_router.add_route("change_model:{rest}", handle_ai_callback)
callback_router.add_route("cancel_set_prompt:{rest}", handle_ai_callback)
callback_router.add_route("cancel_set_summary:{rest}", handle_ai_callback)
callback_router.add_route("summary_now:{rest}", handle_ai_callback)
callback_router.add_route("model_page:{rest}", handle_ai_callback)
callback_router.add_route("select_model:{rest}", handle_ai_callback)
callback_router.add_route("time_page:{rest}", handle_ai_callback)
callback_router.add_route("select_time:{rest}", handle_ai_callback)

# [Fix] 补全 Push 设置相关路由
callback_router.add_route("toggle_push_config:{rest}", handle_push_callback)
callback_router.add_route("delete_push_config:{rest}", handle_push_callback)
callback_router.add_route("push_page:{rest}", handle_push_callback)
callback_router.add_route("cancel_add_push_channel:{rest}", handle_push_callback)
callback_router.add_route("add_push_channel:{rest}", handle_push_callback)
callback_router.add_route("toggle_push_config_status:{rest}", handle_push_callback)

# [Fix] 补全高级媒体筛选相关路由
callback_router.add_route("cancel_set_duration_range:{rest}", callback_cancel_set_duration_range)
callback_router.add_route("cancel_set_resolution_range:{rest}", callback_cancel_set_resolution_range)
callback_router.add_route("cancel_set_file_size_range:{rest}", callback_cancel_set_file_size_range)
callback_router.add_route("set_duration_range:{rest}", callback_set_duration_range)
callback_router.add_route("set_resolution_range:{rest}", callback_set_resolution_range)
callback_router.add_route("set_file_size_range:{rest}", callback_set_file_size_range)
callback_router.add_route("open_duration_picker:{rest}", handle_advanced_media_callback)

# [Fix] 补全 Other 设置相关路由 (模板、去重、复制等)
callback_router.add_route("cancel_set_userinfo:{rest}", handle_other_callback)
callback_router.add_route("cancel_set_time:{rest}", handle_other_callback)
callback_router.add_route("cancel_set_link:{rest}", handle_other_callback)
callback_router.add_route("set_userinfo_template:{rest}", handle_other_callback)
callback_router.add_route("set_time_template:{rest}", handle_other_callback)
callback_router.add_route("set_original_link_template:{rest}", handle_other_callback)

callback_router.add_route("dedup_scan_now:{rest}", handle_other_callback)
callback_router.add_route("delete_duplicates:{rest}", handle_other_callback)
callback_router.add_route("confirm_delete_duplicates:{rest}", handle_other_callback)
callback_router.add_route("view_source_messages:{rest}", handle_other_callback)
callback_router.add_route("keep_duplicates:{rest}", handle_other_callback)
callback_router.add_route("toggle_allow_delete_source_on_dedup:{rest}", handle_other_callback)

callback_router.add_route("other_settings:{rest}", handle_other_callback)
callback_router.add_route("copy_rule:{rest}", handle_other_callback)
callback_router.add_route("copy_keyword:{rest}", handle_other_callback)
callback_router.add_route("perform_copy_rule:{rest}", handle_other_callback)
callback_router.add_route("perform_copy_keyword:{rest}", handle_other_callback)
callback_router.add_route("delete_rule:{rest}", handle_other_callback)
callback_router.add_route("perform_delete_rule:{rest}", handle_other_callback)
callback_router.add_route("ufb_item:{rest}", handle_other_callback)


# 更新日志翻页
from handlers.button.callback.modules.changelog_callback import callback_changelog_page
callback_router.add_route("cl_page:{page}", callback_changelog_page)

# 确认更新与回滚
from handlers.commands.system_commands import (
    callback_confirm_update,
    callback_confirm_rollback
)
callback_router.add_route("confirm_update", callback_confirm_update)
callback_router.add_route("confirm_update:{target}", callback_confirm_update)
callback_router.add_route("confirm_rollback", callback_confirm_rollback)

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
            
        # [Fix] 顺调机制与兼容性增强 (兼容 5 参数的旧版模块化处理器)
        import inspect
        sig = inspect.signature(handler)
        if len(sig.parameters) == 5:
            # 1. 智能提取 rule_id (或者 action 相关的 ID)
            rule_id = params.get('id') or params.get('rule_id')
            if not rule_id and ":" in data:
                parts = data.split(":")
                if len(parts) > 1:
                    rule_id = parts[1]
            
            # 2. 权限安全检查 (若是管理员操作)
            is_admin_action = data.startswith("admin_") or data == "close_admin_panel"
            if is_admin_action:
                from core.helpers.common import is_admin
                if not await is_admin(event):
                    await event.answer("⚠️ 权限不足：仅限管理员", alert=True)
                    return

            # 3. 参数校验 (非管理操作且非取消操作时，rule_id 通常是必须的)
            if not rule_id and not is_admin_action and "cancel" not in data and "noop" not in data:
                logger.warning(f"由于缺失业务 ID，回调分发终止: {data}")
                await event.answer("无效的指令参数", alert=True)
                return

            # 4. 提供统一的 Session 环境，确保模块化处理器高效运行
            async with container.db.get_session() as session:
                message = await event.get_message()
                # 传入转换后的参数
                return await handler(event, rule_id, session, message, data)

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
