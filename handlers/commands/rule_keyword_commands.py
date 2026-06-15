import shlex
from core.logging import get_logger
from core.helpers.error_handler import handle_errors
from core.helpers.auto_delete import async_delete_user_message, reply_and_delete
from services.rule_management_service import rule_management_service
from services.rule_service import RuleQueryService
from enums.enums import AddMode

logger = get_logger(__name__)


@handle_errors(default_return=None)
async def handle_add_command(event, command, parts):
    message_text = event.message.text
    logger.log_operation("处理添加关键字命令", details=f"命令: {command}")
    if len(message_text.split(None, 1)) < 2:
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, f"用法: /{command} <关键字1> [关键字2] ...\n例如:\n/{command} keyword1 \"key word 2\" 'key word 3'")
        return
    from handlers.commands.rule_commands import _parse_keywords
    keywords = await _parse_keywords(message_text, command, parts, event)
    if not keywords:
        return
    from handlers.commands.rule_commands import _add_keywords_to_rule
    result = await _add_keywords_to_rule(keywords, command, event)
    if result:
        rule, source_chat, add_result = result
        await reply_and_delete(event, add_result.get('message', '关键字添加成功'))


async def handle_replace_command(event, parts):
    message_text = event.message.text
    try:
        _, args_text = message_text.split(None, 1)
        r_parts = args_text.split(None, 1)
        pattern = r_parts[0]
        content = r_parts[1] if len(r_parts) > 1 else ""
    except Exception:
        await reply_and_delete(event, "用法: /replace <匹配规则> [替换内容]")
        return
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        result = await container.rule_management_service.add_replace_rules(
            rule_id=rule.id, patterns=[pattern], replacements=[content], is_regex=False
        )
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        action = "删除" if not content else "替换"
        msg = f"✅ 已添加替换规则到 {source_chat.name}:\n匹配: {pattern}\n动作: {action}\n"
        if content:
            msg += f"替换为: {content}"
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 添加替换规则失败: {result.get('error')}")


async def handle_list_keyword_command(event):
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        is_blacklist = rule.add_mode == AddMode.BLACKLIST
        keywords = await rule_management_service.get_keywords(rule.id, is_blacklist=is_blacklist)
    if not keywords:
        await reply_and_delete(event, f"提示：当前规则 ({source_chat.name}) 没有任何关键字。")
        return
    mode_str = "黑名单" if is_blacklist else "白名单"
    res_text = f"📋 **{source_chat.name} 的关键字列表 ({mode_str}):**\n\n"
    for i, kw in enumerate(keywords, 1):
        type_str = "[正则] " if kw.is_regex else ""
        res_text += f"{i}. {type_str}`{kw.keyword}`\n"
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    await reply_and_delete(event, res_text)


async def handle_list_replace_command(event):
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        replace_rules = await rule_management_service.get_replace_rules(rule.id)
    if not replace_rules:
        await reply_and_delete(event, f"提示：当前规则 ({source_chat.name}) 没有任何替换规则。")
        return
    res_text = f"📋 **{source_chat.name} 的替换规则列表:**\n\n"
    for i, r in enumerate(replace_rules, 1):
        action = "删除" if not r.content else f"替换为 `{r.content}`"
        res_text += f"{i}. 匹配 `{r.pattern}` -> {action}\n"
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    await reply_and_delete(event, res_text)


async def handle_remove_command(event, command, parts):
    message_text = event.message.text
    ids_to_remove = []
    keywords_to_remove = []
    is_remove_by_id = command in ["remove_replace", "remove_keyword_by_id", "rkbi"]
    if is_remove_by_id:
        if len(parts) < 2:
            await reply_and_delete(event, f"用法: /{command} <序号1> [序号2] ...")
            return
        try:
            ids_to_remove = [int(x) for x in parts[1:]]
        except ValueError:
            await reply_and_delete(event, "序号必须是数字")
            return
    elif command == "remove_keyword":
        try:
            _, args_text = message_text.split(None, 1)
            keywords_to_remove = shlex.split(args_text)
        except Exception:
            await reply_and_delete(event, f"用法: /{command} <关键字1> ...")
            return
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        if is_remove_by_id:
            if command in ["remove_keyword_by_id", "rkbi"]:
                is_blacklist = rule.add_mode == AddMode.BLACKLIST
                items = await rule_management_service.get_keywords(rule.id, is_blacklist=is_blacklist)
                targets = [items[i-1].keyword for i in ids_to_remove if 1 <= i <= len(items)]
                if targets:
                    result = await container.rule_management_service.delete_keywords(rule.id, targets)
                else:
                    await reply_and_delete(event, "❌ 无效序号")
                    return
            else:
                items = await rule_management_service.get_replace_rules(rule.id)
                targets = [items[i-1].pattern for i in ids_to_remove if 1 <= i <= len(items)]
                if targets:
                    result = await container.rule_management_service.delete_replace_rules(rule.id, targets)
                else:
                    await reply_and_delete(event, "❌ 无效序号")
                    return
        else:
            result = await container.rule_management_service.delete_keywords(rule.id, keywords_to_remove)
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        await reply_and_delete(event, f"✅ 已成功删除指定项目")
    else:
        await reply_and_delete(event, f"❌ 删除失败: {result.get('error')}")


async def handle_clear_all_keywords_command(event, command):
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则。")
            return
        rule, source_chat = rule_info
    result = await rule_management_service.clear_keywords(rule_id=rule.id)
    if result.get('success'):
        msg = f"✅ {result['message']}\n源聊天: {source_chat.name}"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 清除失败: {result.get('error', '未知错误')}")


async def handle_clear_all_keywords_regex_command(event, command):
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则。")
            return
        rule, source_chat = rule_info
    result = await rule_management_service.clear_keywords(rule_id=rule.id, is_regex=True)
    if result.get('success'):
        msg = f"✅ {result['message']}\n源聊天: {source_chat.name}"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 清除正则关键字失败: {result.get('error', '未知错误')}")


async def handle_clear_all_replace_command(event, command):
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则。")
            return
        rule, _ = rule_info
    result = await rule_management_service.clear_replace_rules(rule_id=rule.id)
    if result.get('success'):
        msg = f"✅ {result['message']}\n已自动关闭该规则的替换模式"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 清除失败: {result.get('error', '未知错误')}")
