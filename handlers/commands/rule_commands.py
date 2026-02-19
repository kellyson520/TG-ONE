import shlex
from telethon import Button
# Removed: from sqlalchemy import select (Handler Purity Compliance)
from core.logging import get_logger, log_performance, log_user_action
from core.helpers.error_handler import handle_errors
from core.helpers.auto_delete import async_delete_user_message, reply_and_delete
from services.rule_management_service import rule_management_service
from services.rule_service import RuleQueryService
from enums.enums import AddMode
import os
from core.constants import TEMP_DIR, RSS_HOST, RSS_PORT
from core.helpers.media.excel_importer import parse_excel
from version import VERSION
from core.helpers.auto_delete import respond_and_delete # Alias if needed, or check usages
# Removed: from models.models import ReplaceRule, Keyword (Handler Purity Compliance)
from core.container import container # Used extensively in restored functions

logger = get_logger(__name__)

# Helper to avoid repetitive code in restored functions if they use container directly
async def _get_current_rule_for_chat(event):
    """获取当前聊天的当前选中规则 (使用 Service 层)"""
    return await RuleQueryService.get_current_rule_for_chat(event)


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

    # 2. 获取当前聊天记录以确定选中的规则 (使用Repository)
    from core.container import container
    # 使用RuleRepo提供的聊天查询方法
    current_chat_db = await container.rule_repo.find_chat_by_telegram_id_internal(str(current_chat_id))

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

    async with container.db.get_session() as session:
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
    async with container.db.get_session() as session:
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
    async with container.db.get_session() as session:
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
    async with container.db.get_session() as session:
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
    async with container.db.get_session() as session:
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


async def handle_export_keyword_command(event, command):
    """处理 export_keyword 命令 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            return
        rule, source_chat = rule_info
        
    # 使用 Service 层导出关键字
    lines = await rule_management_service.export_keywords(rule.id)
    
    if not lines:
        await reply_and_delete(event, "当前规则没有任何关键字")
        return
    
    # 获取所有关键字并按类型分类 (使用Service)
    from services.rule.facade import rule_management_service
    all_keywords = await rule_management_service.get_keywords(rule.id, is_blacklist=None)
    
    normal_lines = []
    regex_lines = []
    for kw in all_keywords:
        line = f"{kw.keyword} {1 if kw.is_blacklist else 0}"
        if kw.is_regex:
            regex_lines.append(line)
        else:
            normal_lines.append(line)
    
    # 写入并发送
    files_to_send = []
    if normal_lines:
        path = os.path.join(TEMP_DIR, "keywords.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(normal_lines))
        files_to_send.append(path)
    if regex_lines:
        path = os.path.join(TEMP_DIR, "regex_keywords.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(regex_lines))
        files_to_send.append(path)
        
    try:
        if files_to_send:
            await event.client.send_file(event.chat_id, files_to_send)
            await respond_and_delete(event, f"规则: {source_chat.name}")
    finally:
        for f in files_to_send:
            if os.path.exists(f): os.remove(f)

async def handle_export_replace_command(event, client):
    """处理 export_replace 命令 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            return
        rule, source_chat = rule_info

        # 1. 导出数据 (通过 Service)
        lines = await rule_management_service.export_replace_rules(rule.id)
        if not lines:
            await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
            await reply_and_delete(event, "当前规则没有任何替换规则")
            return

        # 2. 写入并发送
        replace_file = os.path.join(TEMP_DIR, 'replace_rules.txt')
        with open(replace_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        try:
            await event.client.send_file(event.chat_id, replace_file)
            await respond_and_delete(event, f"规则: {source_chat.name}")
        finally:
            if os.path.exists(replace_file): os.remove(replace_file)

async def handle_import_command(event, command):
    """处理导入命令 - 使用 RuleManagementService"""
    if not event.message.file:
        await reply_and_delete(event, f"请将文件和 /{command} 命令一起发送")
        return

    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            return
        rule, source_chat = rule_info

        file_path = await event.message.download_media(TEMP_DIR)
        try:
            import aiofiles
            async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
                content = await f.read()
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            
            if command == "import_replace":
                result = await rule_management_service.import_replace_rules(rule.id, lines)
                if result.get('success'):
                    await reply_and_delete(event, f"✅ 成功导入 {result['imported_count']} 条替换规则\n规则: 来自 {source_chat.name}")
                else:
                    await reply_and_delete(event, f"❌ 导入失败: {result.get('error')}")
            else:
                is_regex = command == "import_regex_keyword"
                result = await rule_management_service.import_keywords(rule.id, lines, is_regex)
                if result.get('success'):
                    kw_type = "正则表达式" if is_regex else "关键字"
                    await reply_and_delete(event, f"✅ 成功导入 {result['imported_count']} 个{kw_type}\n跳过重复: {result['duplicate_count']} 个\n规则: 来自 {source_chat.name}")
                else:
                    await reply_and_delete(event, f"❌ 导入失败: {result.get('error')}")
        finally:
            if os.path.exists(file_path): os.remove(file_path)

async def handle_import_excel_command(event):
    """处理 /import_excel 命令 - 使用 RuleManagementService"""
    if not getattr(event.message, "file", None):
        await reply_and_delete(event, "请将 .xlsx 文件与 /import_excel 命令一起发送")
        return

    file_path = await event.message.download_media(TEMP_DIR)
    try:
        import aiofiles
        async with aiofiles.open(file_path, "rb") as f:
            content_bytes = await f.read()

        import asyncio
        from functools import partial
        loop = asyncio.get_running_loop()
        try:
            keywords_rows, replacement_rows = await loop.run_in_executor(
                None, partial(parse_excel, content_bytes)
            )
        except Exception as e:
            await reply_and_delete(event, f"解析Excel失败：{str(e)}")
            return

        result = await rule_management_service.import_excel(keywords_rows, replacement_rows)
        if result.get('success'):
            msg = (
                "✅ 导入完成\n"
                f"关键字：成功 {result['kw_success']} / 跳过或无效 {result['kw_failed']}\n"
                f"替换规则：成功 {result['r_success']} / 跳过或无效 {result['r_failed']}"
            )
            await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
            await reply_and_delete(event, msg)
        else:
            await reply_and_delete(event, f"❌ 导入失败: {result.get('error')}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)

async def handle_ufb_bind_command(event, command):
    """处理 ufb_bind 命令 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info

    parts = event.message.text.split()
    if len(parts) < 2:
        await reply_and_delete(event, "用法: /ufb_bind <域名> [类型]")
        return

    domain = parts[1].strip().lower()
    item = parts[2].strip().lower() if len(parts) > 2 else "main"

    valid_items = ["main", "content", "main_username", "content_username"]
    if item not in valid_items:
        await reply_and_delete(
            event, f"类型无效，可选: {', '.join(valid_items)}"
        )
        return

    # 使用 Service 层更新 UFB 设置
    result = await rule_management_service.update_rule(
        rule_id=rule.id,
        ufb_domain=domain,
        ufb_item=item,
        is_ufb=True  # 同时激活 UFB 开关
    )

    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        await reply_and_delete(
            event, f"✅ 已绑定 UFB: {domain} ({item})\n源: {source_chat.name}"
        )
    else:
        await reply_and_delete(event, f"❌ UFB绑定失败: {result.get('error')}")

async def handle_ufb_unbind_command(event, command):
    """处理 ufb_unbind 命令 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        old_domain = rule.ufb_domain

    # 使用 Service 层清除 UFB 设置
    result = await rule_management_service.update_rule(
        rule_id=rule.id,
        ufb_domain=None,
        ufb_item=None,
        is_ufb=False  # 同时关闭 UFB 开关
    )

    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        await reply_and_delete(event, f'✅ 已解绑 UFB: {old_domain or "无"}')
    else:
        await reply_and_delete(event, f"❌ UFB解绑失败: {result.get('error')}")

async def handle_ufb_item_change_command(event, command):
    """处理 ufb_item_change 命令"""

    from core.container import container
    # 从container获取数据库会话
    async with container.db.get_session() as session:
        try:
            rule_info = await _get_current_rule_for_chat(session, event)
            if not rule_info:
                return

            rule, source_chat = rule_info

            # 创建4个按钮
            buttons = [
                [
                    Button.inline("主页关键字", "ufb_item:main"),
                    Button.inline("内容页关键字", "ufb_item:content"),
                ],
                [
                    Button.inline("主页用户名", "ufb_item:main_username"),
                    Button.inline("内容页用户名", "ufb_item:content_username"),
                ],
            ]

            # 发送带按钮的消息
            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(
                event, "请选择要切换的UFB同步配置类型:", buttons=buttons
            )

        except Exception as e:
            await session.rollback()
            logger.error(f"切换UFB配置类型时出错: {str(e)}")
            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(event, "切换UFB配置类型时出错，请检查日志")

async def handle_clear_all_keywords_command(event, command):
    """处理 clear_all_keywords 命令 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则。")
            return
        rule, source_chat = rule_info
        
    # 调用服务
    result = await rule_management_service.clear_keywords(rule_id=rule.id)

    if result.get('success'):
        msg = f"✅ {result['message']}\n源聊天: {source_chat.name}"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 清除失败: {result.get('error', '未知错误')}")

async def handle_clear_all_keywords_regex_command(event, command):
    """处理 clear_all_keywords_regex 命令 - 使用 RuleManagementService"""
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则。")
            return
        rule, source_chat = rule_info

    # 调用服务
    result = await rule_management_service.clear_keywords(rule_id=rule.id, is_regex=True)

    if result.get('success'):
        msg = f"✅ {result['message']}\n源聊天: {source_chat.name}"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 清除正则关键字失败: {result.get('error', '未知错误')}")

async def handle_clear_all_replace_command(event, command):
    """处理 clear_all_replace 命令 - 使用 RuleManagementService"""
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则。")
            return
        rule, _ = rule_info

    # 调用服务
    result = await rule_management_service.clear_replace_rules(rule_id=rule.id)

    if result.get('success'):
        msg = f"✅ {result['message']}\n已自动关闭该规则的替换模式"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 清除失败: {result.get('error', '未知错误')}")

async def handle_copy_keywords_command(event, command):
    """处理 copy_keywords 和 copy_keywords_regex 命令 - 异步重构版"""
    is_regex_cmd = command == "copy_keywords_regex"
    parts = event.message.text.split()

    if len(parts) != 2:
        await reply_and_delete(event, f"用法: /{command} <源规则ID>")
        return

    try:
        source_rule_id = int(parts[1])
    except ValueError:
        await reply_and_delete(event, "规则ID必须是数字")
        return

    try:
        # 1. 获取目标规则
        rule_info = await _get_current_rule_for_chat(event)
        if not rule_info:
            await reply_and_delete(event, "⚠️ 当前聊天未绑定规则或未设置正在管理的源频道，请先使用 /switch 或 /bind")
            return
        target_rule_dto, _ = rule_info

        # 2. 调用服务层执行复制
        result = await rule_management_service.copy_keywords_from_rule(
            source_rule_id=source_rule_id,
            target_rule_id=target_rule_dto.id,
            is_regex=is_regex_cmd
        )

        if not result.get('success'):
            await reply_and_delete(event, f"❌ 复制失败: {result.get('error')}")
            return

        success_count = result.get('added', 0)
        skip_count = result.get('skipped', 0)
        type_str = "正则关键字" if is_regex_cmd else "关键字"

        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(
            event,
            f"✅ 已从规则 `{source_rule_id}` 复制{type_str}到规则 `{target_rule_dto.id}`\n"
            f"成功: {success_count} 个\n"
            f"跳过: {skip_count} 个",
            parse_mode="markdown",
        )

    except Exception as e:
        logger.error(f"复制关键字出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "⚠️ 复制关键字时出错，请检查日志")

async def handle_copy_keywords_regex_command(event, command):
    """处理复制正则关键字命令 - 调用通用处理函数"""
    await handle_copy_keywords_command(event, command)

async def handle_copy_replace_command(event, command):
    """处理复制替换规则命令 - 异步重构版"""
    parts = event.message.text.split()
    if len(parts) != 2:
        await reply_and_delete(event, "用法: /copy_replace <规则ID>")
        return

    try:
        source_rule_id = int(parts[1])
    except ValueError:
        await reply_and_delete(event, "规则ID必须是数字")
        return

    try:
        # 1. 获取目标规则
        rule_info = await _get_current_rule_for_chat(event)
        if not rule_info:
            await reply_and_delete(event, "⚠️ 当前聊天未绑定规则或未设置正在管理的源频道，请先使用 /switch 或 /bind")
            return
        target_rule_dto, _ = rule_info

        # 2. 调用服务层执行复制
        result = await rule_management_service.copy_replace_rules_from_rule(
            source_rule_id=source_rule_id,
            target_rule_id=target_rule_dto.id
        )

        if not result.get('success'):
            await reply_and_delete(event, f"❌ 复制失败: {result.get('error')}")
            return

        success_count = result.get('added', 0)
        skip_count = result.get('skipped', 0)

        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(
            event,
            f"✅ 已从规则 `{source_rule_id}` 复制替换规则到规则 `{target_rule_dto.id}`\n"
            f"成功复制: {success_count} 个\n"
            f"跳过重复: {skip_count} 个\n",
            parse_mode="markdown",
        )

    except Exception as e:
        logger.error(f"复制替换规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "⚠️ 复制替换规则时出错，请检查日志")

async def handle_copy_rule_command(event, command):
    """处理复制规则命令 - 异步重构版 (使用 RuleManagementService)"""
    parts = event.message.text.split()

    if len(parts) not in [2, 3]:
        await reply_and_delete(event, "用法: /copy_rule <源规则ID> [目标规则ID]")
        return

    try:
        source_rule_id = int(parts[1])
        target_rule_id = int(parts[2]) if len(parts) == 3 else None
    except ValueError:
        await reply_and_delete(event, "规则ID必须是数字")
        return

    try:
        # 调用 RuleManagementService.copy_rule 方法
        result = await container.rule_management_service.copy_rule(source_rule_id, target_rule_id)
        
        if result.get('success'):
            await reply_and_delete(event, f"规则复制成功！新规则ID: {result.get('new_rule_id')}")
        else:
            await reply_and_delete(event, f"规则复制失败: {result.get('error')}")
    except Exception as e:
        logger.error(f"复制规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "复制规则时出错，请检查日志")

async def handle_remove_all_keyword_command(event, command, parts):
    """处理 remove_all_keyword 命令 - 异步重构版"""
    message_text = event.message.text
    if len(message_text.split(None, 1)) < 2:
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, f"用法: /{command} <关键字1> [关键字2] ...")
        return

    _, args_text = message_text.split(None, 1)
    try:
        keywords = shlex.split(args_text)
    except ValueError:
        await reply_and_delete(event, "参数格式错误：请确保引号正确配对")
        return

    if not keywords:
        await reply_and_delete(event, "请提供至少一个关键字")
        return

    # 调用服务
    result = await rule_management_service.delete_keywords_all_rules(keywords=keywords)

    if result.get('success'):
        msg = f"✅ {result['message']}"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 批量删除失败: {result.get('error', '未知错误')}")

async def handle_add_all_command(event, command, parts):
    """处理 add_all 和 add_regex_all 命令 - 异步重构版"""
    message_text = event.message.text
    if len(message_text.split(None, 1)) < 2:
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, f"用法: /{command} <关键字1> [关键字2] ...")
        return

    _, args_text = message_text.split(None, 1)
    is_regex = (command == "add_regex_all")

    try:
        if not is_regex:
            keywords = shlex.split(args_text)
        else:
            keywords = args_text.split() if len(args_text.split()) > 0 else [args_text]
    except ValueError:
        await reply_and_delete(event, "参数格式错误：请确保引号正确配对")
        return

    if not keywords:
        await reply_and_delete(event, "请提供至少一个关键字")
        return

    # 获取当前规则以确定 AddMode (黑/白名单)
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则，无法确定添加模式。")
            return
        
        current_rule, _ = rule_info
        is_blacklist = current_rule.add_mode == AddMode.BLACKLIST

    # 调用服务执行批量添加
    result = await rule_management_service.add_keywords_all_rules(
        keywords=keywords,
        is_regex=is_regex,
        is_blacklist=is_blacklist
    )

    if result.get('success'):
        keyword_type = "正则表达式" if is_regex else "关键字"
        keywords_text = "\n".join(f"- {k}" for k in keywords)
        msg = f"✅ {result['message']}\n类型: {keyword_type}\n同步规则数: {result.get('rule_count', 0)}\n列表:\n{keywords_text}"
        
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 批量添加失败: {result.get('error', '未知错误')}")

async def handle_replace_all_command(event, parts):
    """处理 replace_all 命令 - 异步重构版"""
    message_text = event.message.text
    if len(message_text.split(None, 1)) < 2:
        await reply_and_delete(event, "用法: /replace_all <匹配规则> [替换内容]")
        return

    _, args_text = message_text.split(None, 1)
    # 简单解析 pattern 和 content
    args_parts = args_text.split(None, 1)
    pattern = args_parts[0]
    content = args_parts[1] if len(args_parts) > 1 else ""

    # 调用服务
    result = await rule_management_service.add_replace_rules_all_rules(
        patterns=[pattern],
        replacements=[content],
        is_regex=True # replace_all 默认通常是正则，或者根据具体逻辑确定
    )

    if result.get('success'):
        action_type = "删除" if not content else "替换"
        msg = f"✅ {result['message']}\n匹配模式: {pattern}\n动作: {action_type}"
        if content:
            msg += f"\n替换为: {content}"
        
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 批量添加失败: {result.get('error', '未知错误')}")

async def handle_delete_rule_command(event, command, parts):
    """处理 delete_rule 命令 - 异步重构版"""
    if len(parts) < 2:
        await reply_and_delete(event, f"用法: /{command} <ID1> [ID2] ...")
        return

    try:
        ids_to_remove = [int(x) for x in parts[1:]]
    except ValueError:
        await reply_and_delete(event, "ID必须是数字")
        return

    try:
        success_ids = []
        failed_ids = []
        not_found_ids = []

        for rule_id in ids_to_remove:
            # ✅ 使用 Service 删除规则
            result = await container.rule_management_service.delete_rule(rule_id)

            if result["success"]:
                success_ids.append(rule_id)

                # 异步 RSS 删除调用 (保持非阻塞)
                # 将 HTTP 请求放入后台任务，或在此处异步等待
                try:
                    import aiohttp

                    rss_url = f"http://{RSS_HOST}:{RSS_PORT}/api/rule/{rule_id}"
                    # 使用极短超时，避免阻塞删除流程
                    timeout = aiohttp.ClientTimeout(total=2)
                    async with aiohttp.ClientSession(timeout=timeout) as client_session:
                        async with client_session.delete(rss_url) as response:
                            if response.status != 200:
                                logger.warning(f"RSS同步删除失败: {response.status}")
                except ImportError as e:
                    logger.debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
                except Exception as rss_e:
                    logger.warning(f"RSS同步删除出错: {rss_e}")
            else:
                if "error" in result and "规则不存在" in result["error"]:
                    not_found_ids.append(rule_id)
                else:
                    failed_ids.append(rule_id)

        # 构建响应消息
        response_parts = []
        if success_ids:
            response_parts.append(f'✅ 成功删除: {", ".join(map(str, success_ids))}')
        if not_found_ids:
            response_parts.append(f'❓ 未找到: {", ".join(map(str, not_found_ids))}')
        if failed_ids:
            response_parts.append(f'❌ 删除失败: {", ".join(map(str, failed_ids))}')

        await async_delete_user_message(
            event.client, event.message.chat_id, event.message.id, 0
        )
        await reply_and_delete(event, "\n".join(response_parts) or "没有规则被删除")

    except Exception as e:
        logger.error(f"删除规则时发生致命错误: {str(e)}")
        await reply_and_delete(event, "删除规则时发生错误，请检查日志")

async def handle_list_rule_command(event, command, parts):
    """处理 list_rule 命令 - 异步分页重构版"""
    try:
        # 解析页码
        try:
            page = int(parts[1]) if len(parts) > 1 else 1
            if page < 1:
                page = 1
        except ValueError:
            await reply_and_delete(event, "页码必须是数字")
            return

        per_page = 30

        # ✅ 使用 Repository 获取数据，而不是自己写 SQL
        rules, total_rules = await container.rule_repo.get_all(page, per_page)

        if not rules:
            await reply_and_delete(event, "当前没有任何转发规则")
            return

        total_pages = (total_rules + per_page - 1) // per_page
        if page > total_pages:
            page = total_pages
            rules, total_rules = await container.rule_repo.get_all(page, per_page)

            # 3. 构建消息
            message_parts = [f"📋 转发规则列表 (第{page}/{total_pages}页)：\n"]

            for rule in rules:
                # 因为使用了 selectinload，这里访问 source_chat 不会阻塞或报错
                source_name = rule.source_chat.name if rule.source_chat else "Unknown"
                source_tid = (
                    rule.source_chat.telegram_chat_id if rule.source_chat else "N/A"
                )
                target_name = rule.target_chat.name if rule.target_chat else "Unknown"
                target_tid = (
                    rule.target_chat.telegram_chat_id if rule.target_chat else "N/A"
                )

                rule_desc = (
                    f"<b>ID: {rule.id}</b>\n"
                    f"<blockquote>来源: {source_name} ({source_tid})\n"
                    f"目标: {target_name} ({target_tid})\n"
                    "</blockquote>"
                )
                message_parts.append(rule_desc)

            # 4. 构建按钮
            buttons = []
            nav_row = []
            if page > 1:
                nav_row.append(Button.inline("⬅️ 上一页", f"page_rule:{page-1}"))
            else:
                nav_row.append(Button.inline("⬅️", "noop"))
            nav_row.append(Button.inline(f"{page}/{total_pages}", "noop"))
            if page < total_pages:
                nav_row.append(Button.inline("下一页 ➡️", f"page_rule:{page+1}"))
            else:
                nav_row.append(Button.inline("➡️", "noop"))
            buttons.append(nav_row)

            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(
                event, "\n".join(message_parts), buttons=buttons, parse_mode="html"
            )

    except Exception as e:
        logger.error(f"列出规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "获取规则列表时发生错误，请检查日志")

async def handle_delete_rss_user_command(event, command, parts):
    """处理 delete_rss_user 命令 - 使用UserService重构版"""
    from services.user_service import user_service
    
    try:
        specified_username = parts[1].strip() if len(parts) > 1 else None

        # 获取所有用户
        all_users = await user_service.get_all_users()

        if not all_users:
            await reply_and_delete(event, "RSS系统中没有用户账户")
            return

        # 指定用户名删除
        if specified_username:
            result = await user_service.delete_user_by_username(specified_username)

            if result.get('success'):
                await reply_and_delete(
                    event, f"已删除RSS用户: {specified_username}"
                )
            else:
                await reply_and_delete(
                    event, f"未找到用户名为 '{specified_username}' 的RSS用户"
                )
            return

        # 未指定且只有一个用户
        if len(all_users) == 1:
            username = all_users[0].username
            result = await user_service.delete_user_by_username(username)
            if result.get('success'):
                await reply_and_delete(event, f"已删除RSS用户: {username}")
            else:
                await reply_and_delete(event, f"删除失败: {result.get('error')}")
            return

        # 多个用户列表展示
        usernames = [u.username for u in all_users]
        user_list = "\n".join(
            [f"{i+1}. {name}" for i, name in enumerate(usernames)]
        )
        await reply_and_delete(
            event,
            f"请指定要删除的用户名:\n/delete_rss_user <用户名>\n\n现有用户:\n{user_list}",
        )

    except Exception as e:
        logger.error(f"删除RSS用户时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "删除RSS用户失败，请查看日志")


async def handle_help_command(event, command):
    """处理帮助命令"""
    help_text = (
        f"🤖 **Telegram 消息转发机器人 v{VERSION}**\n\n"
        "**基础命令**\n"
        "/start - 开始使用\n"
        "/help(/h) - 显示此帮助信息\n\n"
        "**绑定和设置**\n"
        "/bind(/b) <源聊天链接或名称> [目标聊天链接或名称] - 绑定源聊天\n"
        "/settings(/s) [规则ID] - 管理转发规则\n"
        "/changelog(/cl) - 查看更新日志\n\n"
        "**转发规则管理**\n"
        "/copy_rule(/cr)  <源规则ID> [目标规则ID] - 复制指定规则的所有设置到当前规则或目标规则ID\n"
        "/list_rule(/lr) - 列出所有转发规则\n"
        "/delete_rule(/dr) <规则ID> [规则ID] [规则ID] ... - 删除指定规则\n\n"
        "**关键字管理**\n"
        "/add(/a) <关键字> [关键字] [\"关 键 字\"] ['关 键 字'] ... - 添加普通关键字\n"
        "/add_regex(/ar) <正则表达式> [正则表达式] [正则表达式] ... - 添加正则表达式\n"
        "/add_all(/aa) <关键字> [关键字] [关键字] ... - 添加普通关键字到当前频道绑定的所有规则\n"
        "/add_regex_all(/ara) <正则表达式> [正则表达式] [正则表达式] ... - 添加正则表达式到所有规则\n"
        "/list_keyword(/lk) - 列出所有关键字\n"
        "/remove_keyword(/rk) <关键词1> [\"关 键 字\"] ['关 键 字'] ... - 删除关键字\n"
        "/remove_keyword_by_id(/rkbi) <ID> [ID] [ID] ... - 按ID删除关键字\n"
        "/remove_all_keyword(/rak) [关键字] [\"关 键 字\"] ['关 键 字'] ... - 删除当前频道绑定的所有规则的指定关键字\n"
        "/clear_all_keywords(/cak) - 清除当前规则的所有关键字\n"
        "/clear_all_keywords_regex(/cakr) - 清除当前规则的所有正则关键字\n"
        "/copy_keywords(/ck) <规则ID> - 复制指定规则的关键字到当前规则\n"
        "/copy_keywords_regex(/ckr) <规则ID> - 复制指定规则的正则关键字到当前规则\n\n"
        "**替换规则管理**\n"
        "/replace(/r) <正则表达式> [替换内容] - 添加替换规则\n"
        "/replace_all(/ra) <正则表达式> [替换内容] - 添加替换规则到所有规则\n"
        "/list_replace(/lrp) - 列出所有替换规则\n"
        "/remove_replace(/rr) <序号> - 删除替换规则\n"
        "/clear_all_replace(/car) - 清除当前规则的所有替换规则\n"
        "/copy_replace(/crp) <规则ID> - 复制指定规则的替换规则到当前规则\n\n"
        "**导入导出**\n"
        "/export_keyword(/ek) - 导出当前规则的关键字\n"
        "/export_replace(/er) - 导出当前规则的替换规则\n"
        "/import_keyword(/ik) <同时发送文件> - 导入普通关键字\n"
        "/import_regex_keyword(/irk) <同时发送文件> - 导入正则关键字\n"
        "/import_replace(/ir) <同时发送文件> - 导入替换规则\n"
        "/import_excel <同时发送xlsx文件> - 一次性导入关键字与替换规则\n\n"
        "**转发记录查询**\n"
        "/forward_stats(/fs) [日期] - 查看转发统计 (如: /fs 2024-01-15)\n"
        "/forward_search(/fsr) [参数] - 搜索转发记录\n"
        "  参数格式: chat:聊天ID user:用户ID type:消息类型 rule:规则ID date:日期 limit:数量\n"
        "  例: /fsr chat:-1001234567 type:video limit:5\n\n"
        "**RSS相关**\n"
        "/delete_rss_user(/dru) [用户名] - 删除RSS用户\n"
        "**去重相关**\n"
        "/dedup - 切换当前规则的去重开关\n"
        "/dedup_center(/dc) - 智能去重中心 (GUI 概览)\n"
        "/smart_dedup(/sd) - 智能去重高级策略设置\n"
        "/clear_dedup_cache(/cdc) - 一键清除去重缓存集\n"
        "/dedup_scan - 扫描当前目标会话的重复媒体\n\n"
        "**数据库管理**\n"
        "/db_info - 查看数据库信息\n"
        "/db_backup - 备份数据库\n"
        "/db_optimize - 优化数据库\n"
        "/db_health - 数据库健康检查\n\n"
        "**系统管理**\n"
        "/system_status - 查看系统状态\n"
        "/admin - 系统管理面板\n"
        "/logs - 查看系统日志 (支持 error 参数查看错误日志)\n"
        "/download_logs - 下载完整系统日志\n\n"
        "**UFB相关**\n"
        "/ufb_bind(/ub) <域名> - 绑定UFB域名\n"
        "/ufb_unbind(/uu) - 解绑UFB域名\n"
        "/ufb_item_change(/uic) - 切换UFB同步配置类型\n\n"
        "💡 **提示**\n"
        "• 括号内为命令的简写形式\n"
        "• 尖括号 <> 表示必填参数\n"
        "• 方括号 [] 表示可选参数\n"
        "• 导入命令需要同时发送文件"
    )

    await async_delete_user_message(
        event.client, event.message.chat_id, event.message.id, 0
    )

    await async_delete_user_message(
        event.client, event.message.chat_id, event.message.id, 0
    )
    await reply_and_delete(event, help_text, parse_mode="markdown")


# =================== 去重命令实现 ===================

async def handle_start_command(event):
    """处理 start 命令"""

    welcome_text = f"""
    👋 欢迎使用 Telegram 消息转发机器人！
    
    📱 当前版本：v{VERSION}

    📖 查看完整命令列表请使用 /help

    """
    await async_delete_user_message(
        event.client, event.message.chat_id, event.message.id, 0
    )
    await reply_and_delete(event, welcome_text)

async def handle_changelog_command(event):
    """处理 changelog 命令"""
    await async_delete_user_message(
        event.client, event.message.chat_id, event.message.id, 0
    )
    # 使用分页显示逻辑
    from handlers.button.callback.modules.changelog_callback import show_changelog
    await show_changelog(event, page=1)


# =================== 搜索命令实现 ===================

async def _common_search_handler(event, parts, search_type):
    """通用搜索处理函数"""
    from handlers.search_ui_manager import SearchUIManager
    from core.helpers.search_system import SearchFilter, get_search_system
    from core.container import container
    from core.helpers.auto_delete import reply_and_delete, async_delete_user_message

    if len(parts) < 2:
        await reply_and_delete(event, f"🔍 用法: /{event.message.text.split()[0][1:]} <关键词>")
        return

    query = " ".join(parts[1:])
    
    # 获取搜索系统（集成用户客户端）
    search_system = get_search_system(container.user_client)
    
    # 构建筛选器
    filters = SearchFilter(search_type=search_type)
    
    # 执行搜索
    response = await search_system.search(query, filters, 1)
    
    # 生成界面
    message_text = SearchUIManager.generate_search_message(response)
    buttons = SearchUIManager.generate_pagination_buttons(response, "search")
    
    # 删除指令并回复
    try:
        await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    except Exception:
        pass
    await reply_and_delete(event, message_text, buttons=buttons, parse_mode="html")


async def handle_search_command(event, command, parts):
    """处理 /search 命令 - 全局聚合搜索"""
    from core.helpers.search_system import SearchType
    await _common_search_handler(event, parts, SearchType.ALL)


async def handle_search_bound_command(event, command, parts):
    """处理 /search_bound 命令 - 在绑定频道搜索"""
    from core.helpers.search_system import SearchType
    await _common_search_handler(event, parts, SearchType.BOUND_CHATS)


async def handle_search_public_command(event, command, parts):
    """处理 /search_public 命令 - 搜索公开频道"""
    from core.helpers.search_system import SearchType
    await _common_search_handler(event, parts, SearchType.PUBLIC_CHATS)


async def handle_search_all_command(event, command, parts):
    """处理 /search_all 命令 - 全局聚合搜索"""
    from core.helpers.search_system import SearchType
    await _common_search_handler(event, parts, SearchType.ALL)