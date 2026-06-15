import shlex
from core.logging import get_logger, log_performance, log_user_action
from core.helpers.error_handler import handle_errors
from core.helpers.auto_delete import async_delete_user_message, reply_and_delete
from services.rule_management_service import rule_management_service
from services.rule_service import RuleQueryService
from core.container import container

logger = get_logger(__name__)


async def _get_current_rule_for_chat(event):
    return await RuleQueryService.get_current_rule_for_chat(event)


async def handle_bind_command(event, client, parts):
    message_text = event.message.text
    try:
        if " " in message_text:
            command, args_str = message_text.split(" ", 1)
            args = shlex.split(args_str)
            if len(args) >= 1:
                source_input = args[0]
                target_input = args[1] if len(args) >= 2 else None
            else:
                raise ValueError("参数不足")
        else:
            raise ValueError("参数不足")
    except ValueError:
        await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
        await reply_and_delete(
            event,
            '用法: /bind <源聊天链接或名称> [目标聊天链接或名称]\n例如:\n/bind https://t.me/channel_name\n/bind "频道 名称"\n/bind https://t.me/source_channel https://t.me/target_channel',
        )
        return
    from core.container import container
    user_client = container.user_client
    result = await rule_management_service.bind_chat(
        user_client, source_input, target_input, current_chat_id=event.chat_id
    )
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        msg = (
            f"✅ {'已创建' if result.get('is_new') else '已找到存在'}的转发规则:\n"
            f"源聊天: {result.get('source_name')}\n"
            f"目标聊天: {result.get('target_name')}\n"
            f"请使用 /add 或 /add_regex 添加关键字"
        )
        from telethon import Button
        buttons = [Button.inline("⚙️ 打开设置", f"rule_settings:{result.get('rule_id')}")]
        await reply_and_delete(event, msg, buttons=buttons)
    else:
        await reply_and_delete(event, f"❌ 绑定失败: {result.get('error')}")


@log_performance("处理设置命令", threshold_seconds=3.0)
@log_user_action("设置", extract_user_id=lambda event, command, parts: getattr(event.sender, "id", "unknown"))
@handle_errors(default_return=None)
async def handle_settings_command(event, command, parts):
    logger.log_operation("处理设置命令", details=f"命令: {command}")
    from handlers.button.new_menu_system import new_menu_system
    await new_menu_system.show_main_menu(event)
    try:
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        logger.log_operation("设置命令处理完成", details="菜单显示成功，用户消息已删除")
    except Exception as e:
        logger.log_error("删除用户消息", e)


@log_performance("处理切换命令", threshold_seconds=3.0)
@log_user_action("切换规则", extract_user_id=lambda event: getattr(event.sender, "id", "unknown"))
@handle_errors(default_return=None)
async def handle_switch_command(event):
    current_chat = await event.get_chat()
    current_chat_id = current_chat.id
    logger.log_operation("处理切换命令", details=f"聊天ID: {current_chat_id}")
    rules = await RuleQueryService.get_rules_for_target_chat(current_chat_id)
    if not rules:
        await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
        await reply_and_delete(event, "❌ 当前聊天没有任何转发规则\n提示：使用 /bind @源聊天 来创建规则，或在目标聊天中使用此命令")
        return
    from core.container import container
    current_chat_db = await container.rule_repo.find_chat_by_telegram_id_internal(str(current_chat_id))
    from telethon import Button
    buttons = []
    for rule in rules:
        source_chat = rule.source_chat
        if not source_chat:
            continue
        is_current = False
        if current_chat_db and current_chat_db.current_add_id == source_chat.telegram_chat_id:
            is_current = True
        button_text = f'{"✓ " if is_current else ""}来自: {source_chat.name}'
        callback_data = f"switch:{source_chat.telegram_chat_id}"
        buttons.append([Button.inline(button_text, callback_data)])
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    await reply_and_delete(event, "请选择要管理的转发规则:", buttons=buttons)


@log_performance("添加关键字", threshold_seconds=5.0)
async def _parse_keywords(message_text, command, parts, event):
    try:
        if " " not in message_text:
            return []
        _, args_text = message_text.split(None, 1)
        if command == "add" or command == "add_all":
            return shlex.split(args_text)
        else:
            try:
                kw_list = args_text.split()
                return kw_list if kw_list else [args_text]
            except Exception:
                return [args_text]
    except Exception as e:
        logger.error(f"解析参数失败: {e}")
        from core.helpers.auto_delete import reply_and_delete
        await reply_and_delete(event, "参数格式错误：请确认引号是否正确配对")
        return []


async def _add_keywords_to_rule(keywords, command, event):
    from core.container import container
    from enums.enums import AddMode
    from services.rule_service import RuleQueryService
    from services.rule_management_service import rule_management_service
    from core.helpers.auto_delete import reply_and_delete
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return None
        rule, source_chat = rule_info
        is_regex = "regex" in command
        is_blacklist = rule.add_mode == AddMode.BLACKLIST
        result = await rule_management_service.add_keywords(
            rule_id=rule.id, keywords=keywords, is_regex=is_regex, is_negative=is_blacklist
        )
        return rule, source_chat, result


# Re-export from split modules
from handlers.commands.rule_keyword_commands import (
    handle_add_command,
    handle_replace_command,
    handle_list_keyword_command,
    handle_list_replace_command,
    handle_remove_command,
    handle_clear_all_keywords_command,
    handle_clear_all_keywords_regex_command,
    handle_clear_all_replace_command,
)
from handlers.commands.rule_bulk_commands import (
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
)
from handlers.commands.rule_admin_commands import (
    handle_clear_all_command,
    handle_export_keyword_command,
    handle_export_replace_command,
    handle_import_command,
    handle_import_excel_command,
    handle_ufb_bind_command,
    handle_ufb_unbind_command,
    handle_ufb_item_change_command,
    handle_help_command,
    handle_start_command,
    handle_changelog_command,
    _common_search_handler,
    handle_search_command,
    handle_search_bound_command,
    handle_search_public_command,
    handle_search_all_command,
)
