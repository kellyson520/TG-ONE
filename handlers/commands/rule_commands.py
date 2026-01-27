import shlex
from telethon import Button
import logging
from sqlalchemy import select
from core.logging import get_logger, log_performance, log_user_action
from core.helpers.error_handler import handle_errors
from core.helpers.auto_delete import async_delete_user_message, reply_and_delete
from services.rule_management_service import rule_management_service
from services.rule_service import RuleQueryService
from enums.enums import AddMode

logger = get_logger(__name__)


async def handle_bind_command(event, client, parts):
    """处理 bind 命令 - 业务逻辑已迁移至 RuleManagementService"""
    message_text = event.message.text
    try:
        # 1. 参数解析
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

    # 2. 调用服务层
    from core.container import container
    user_client = container.user_client
    result = await rule_management_service.bind_chat(
        user_client, 
        source_input, 
        target_input, 
        current_chat_id=event.chat_id
    )

    # 3. 处理结果
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    
    if result.get('success'):
        msg = (
            f"✅ {'已创建' if result.get('is_new') else '已找到存在'}的转发规则:\n"
            f"源聊天: {result.get('source_name')}\n"
            f"目标聊天: {result.get('target_name')}\n"
            f"请使用 /add 或 /add_regex 添加关键字"
        )
        buttons = [Button.inline("⚙️ 打开设置", f"rule_settings:{result.get('rule_id')}")]
        await reply_and_delete(event, msg, buttons=buttons)
    else:
        await reply_and_delete(event, f"❌ 绑定失败: {result.get('error')}")


@log_performance("处理设置命令", threshold_seconds=3.0)
@log_user_action(
    "设置",
    extract_user_id=lambda event, command, parts: getattr(
        event.sender, "id", "unknown"
    ),
)
@handle_errors(default_return=None)
async def handle_settings_command(event, command, parts):
    """处理 settings 命令 - 启动新菜单系统 - 优化版本"""
    logger.log_operation("处理设置命令", details=f"命令: {command}")

    # 显示新的主菜单（延迟导入避免循环依赖）
    from handlers.button.new_menu_system import new_menu_system

    await new_menu_system.show_main_menu(event)

    # 在菜单显示成功后删除用户消息
    try:
        await async_delete_user_message(
            event.client, event.message.chat_id, event.message.id, 0
        )
        logger.log_operation("设置命令处理完成", details="菜单显示成功，用户消息已删除")
    except Exception as e:
        logger.log_error("删除用户消息", e)


@log_performance("处理切换命令", threshold_seconds=3.0)
@log_user_action(
    "切换规则", extract_user_id=lambda event: getattr(event.sender, "id", "unknown")
)
@handle_errors(default_return=None)
async def handle_switch_command(event):
    """处理 switch 命令 - 使用 RuleQueryService 优化交互"""
    current_chat = await event.get_chat()
    current_chat_id = current_chat.id

    logger.log_operation("处理切换命令", details=f"聊天ID: {current_chat_id}")

    # 1. 调用服务层获取作为目标的所有规则
    rules = await RuleQueryService.get_rules_for_target_chat(current_chat_id)

    if not rules:
        await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
        await reply_and_delete(
            event,
            "❌ 当前聊天没有任何转发规则\n提示：使用 /bind @源聊天 来创建规则，或在目标聊天中使用此命令",
        )
        return

    # 2. 获取当前聊天记录以确定选中的规则
    from core.container import container
    async with container.db.session() as session:
        from models.models import Chat
        stmt = select(Chat).where(Chat.telegram_chat_id == str(current_chat_id))
        result = await session.execute(stmt)
        current_chat_db = result.scalar_one_or_none()

    # 3. 创建规则选择按钮
    buttons = []
    for rule in rules:
        source_chat = rule.source_chat
        if not source_chat:
            continue

        is_current = False
        if (
            current_chat_db
            and current_chat_db.current_add_id == source_chat.telegram_chat_id
        ):
            is_current = True

        button_text = f'{"✓ " if is_current else ""}来自: {source_chat.name}'
        callback_data = f"switch:{source_chat.telegram_chat_id}"
        buttons.append([Button.inline(button_text, callback_data)])

    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    await reply_and_delete(event, "请选择要管理的转发规则:", buttons=buttons)


@log_performance("添加关键字", threshold_seconds=5.0)
async def _parse_keywords(message_text, command, parts, event):
    """解析关键字，处理引号"""
    try:
        # 移除命令部分
        if " " not in message_text:
            return []
        _, args_text = message_text.split(None, 1)
        if command == "add" or command == "add_all":
            return shlex.split(args_text)
        else: # add_regex 或 add_regex_all
            # 正则表达式通常不使用 shlex 分割，以防特殊字符被转义
            # 这里简单按空格分割，或者如果报错则整体作为一个
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
    """通用逻辑：获取当前规则并将关键字加入"""
    from core.container import container
    from enums.enums import AddMode
    from services.rule_service import RuleQueryService
    from services.rule_management_service import rule_management_service

    from core.helpers.auto_delete import reply_and_delete

    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return None
        rule, source_chat = rule_info
        
        is_regex = "regex" in command
        is_blacklist = rule.add_mode == AddMode.BLACKLIST
        
        result = await rule_management_service.add_keywords(
            rule_id=rule.id,
            keywords=keywords,
            is_regex=is_regex,
            is_negative=is_blacklist
        )
        return rule, source_chat, result


@log_user_action(
    "添加关键字",
    extract_user_id=lambda event, command, parts: getattr(
        event.sender, "id", "unknown"
    ),
)
@handle_errors(default_return=None)
async def handle_add_command(event, command, parts):
    """处理 add 和 add_regex 命令 - 优化版本"""
    message_text = event.message.text
    logger.log_operation("处理添加关键字命令", details=f"命令: {command}")

    # 验证参数
    if len(message_text.split(None, 1)) < 2:
        await async_delete_user_message(
            event.client, event.message.chat_id, event.message.id, 0
        )
        await reply_and_delete(
            event,
            f"用法: /{command} <关键字1> [关键字2] ...\n例如:\n/{command} keyword1 \"key word 2\" 'key word 3'",
        )
        return

    # 解析关键字
    keywords = await _parse_keywords(message_text, command, parts, event)
    if not keywords:
        return

    # 获取当前规则并添加关键字
    result = await _add_keywords_to_rule(keywords, command, event)
    if result:
        rule, source_chat, add_result = result

        # 发送结果消息
        await reply_and_delete(
            event, 
            add_result.get('message', '关键字添加成功')
        )


async def handle_replace_command(event, parts):
    """处理 replace 命令 - 业务逻辑已迁移至 RuleManagementService"""
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
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        
        result = await container.rule_management_service.add_replace_rules(
            rule_id=rule.id,
            patterns=[pattern],
            replacements=[content],
            is_regex=False
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
    """处理 list_keyword 命令 - 使用统一 Service 获取规则"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        
        is_blacklist = rule.add_mode == AddMode.BLACKLIST
        # Refactored: Call Service instead of direct SQL
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
    """处理 list_replace 命令 - 使用统一 Service 获取规则"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info

        # Refactored: Call Service instead of direct SQL
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
    """处理 remove_keyword 和 remove_replace 命令 - 业务逻辑已迁移至 RuleManagementService"""
    message_text = event.message.text
    ids_to_remove = []
    keywords_to_remove = []

    # 1. 参数解析
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

    # 2. 获取规则上下文
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        
        # 3. 处理按序号删除的映射 (序号 -> 真实内容)
        if is_remove_by_id:
            if command in ["remove_keyword_by_id", "rkbi"]:
                is_blacklist = rule.add_mode == AddMode.BLACKLIST
                # Refactored: Use Service to look up by ID - but service returns DTOs in new list method. 
                # Let's use the list method to get items and then map indices.
                items = await rule_management_service.get_keywords(rule.id, is_blacklist=is_blacklist)
                targets = [items[i-1].keyword for i in ids_to_remove if 1 <= i <= len(items)]
                if targets:
                    result = await container.rule_management_service.delete_keywords(rule.id, targets)
                else:
                    await reply_and_delete(event, "❌ 无效序号")
                    return
            else: # remove_replace
                items = await rule_management_service.get_replace_rules(rule.id)
                targets = [items[i-1].pattern for i in ids_to_remove if 1 <= i <= len(items)]
                if targets:
                    result = await container.rule_management_service.delete_replace_rules(rule.id, targets)
                else:
                    await reply_and_delete(event, "❌ 无效序号")
                    return
        else: # remove_keyword (by text)
            result = await container.rule_management_service.delete_keywords(rule.id, keywords_to_remove)

    # 4. 反馈结果
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        await reply_and_delete(event, f"✅ 已成功删除指定项目")
    else:
        await reply_and_delete(event, f"❌ 删除失败: {result.get('error')}")


async def handle_clear_all_command(event):
    """处理 clear_all 命令 - 使用 RuleManagementService"""
    # 这里通常应该增加一个二次确认逻辑，但为了保持逻辑一致，我们先直接迁移
    result = await rule_management_service.clear_all_data()

    if result.get('success'):
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, f"✅ {result['message']}")
    else:
        await reply_and_delete(event, f"❌ 清空数据失败: {result.get('error', '未知错误')}")
