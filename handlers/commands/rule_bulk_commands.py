import shlex
from telethon import Button
from core.logging import get_logger
from core.helpers.auto_delete import async_delete_user_message, reply_and_delete
from services.rule_management_service import rule_management_service
from services.rule_service import RuleQueryService
from enums.enums import AddMode
from core.constants import RSS_HOST, RSS_PORT
from core.container import container

logger = get_logger(__name__)


async def _get_current_rule_for_chat(event):
    return await RuleQueryService.get_current_rule_for_chat(event)


async def handle_copy_keywords_command(event, command):
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
        rule_info = await _get_current_rule_for_chat(event)
        if not rule_info:
            await reply_and_delete(event, "⚠️ 当前聊天未绑定规则或未设置正在管理的源频道，请先使用 /switch 或 /bind")
            return
        target_rule_dto, _ = rule_info
        result = await rule_management_service.copy_keywords_from_rule(
            source_rule_id=source_rule_id, target_rule_id=target_rule_dto.id, is_regex=is_regex_cmd
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
            f"✅ 已从规则 `{source_rule_id}` 复制{type_str}到规则 `{target_rule_dto.id}`\n成功: {success_count} 个\n跳过: {skip_count} 个",
            parse_mode="markdown",
        )
    except Exception as e:
        logger.error(f"复制关键字出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "⚠️ 复制关键字时出错，请检查日志")


async def handle_copy_keywords_regex_command(event, command):
    await handle_copy_keywords_command(event, command)


async def handle_copy_replace_command(event, command):
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
        rule_info = await _get_current_rule_for_chat(event)
        if not rule_info:
            await reply_and_delete(event, "⚠️ 当前聊天未绑定规则或未设置正在管理的源频道，请先使用 /switch 或 /bind")
            return
        target_rule_dto, _ = rule_info
        result = await rule_management_service.copy_replace_rules_from_rule(
            source_rule_id=source_rule_id, target_rule_id=target_rule_dto.id
        )
        if not result.get('success'):
            await reply_and_delete(event, f"❌ 复制失败: {result.get('error')}")
            return
        success_count = result.get('added', 0)
        skip_count = result.get('skipped', 0)
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(
            event,
            f"✅ 已从规则 `{source_rule_id}` 复制替换规则到规则 `{target_rule_dto.id}`\n成功复制: {success_count} 个\n跳过重复: {skip_count} 个\n",
            parse_mode="markdown",
        )
    except Exception as e:
        logger.error(f"复制替换规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "⚠️ 复制替换规则时出错，请检查日志")


async def handle_copy_rule_command(event, command):
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
        result = await container.rule_management_service.copy_rule(source_rule_id, target_rule_id)
        if result.get('success'):
            await reply_and_delete(event, f"规则复制成功！新规则ID: {result.get('new_rule_id')}")
        else:
            await reply_and_delete(event, f"规则复制失败: {result.get('error')}")
    except Exception as e:
        logger.error(f"复制规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "复制规则时出错，请检查日志")


async def handle_remove_all_keyword_command(event, command, parts):
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
    result = await rule_management_service.delete_keywords_all_rules(keywords=keywords)
    if result.get('success'):
        msg = f"✅ {result['message']}"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 批量删除失败: {result.get('error', '未知错误')}")


async def handle_add_all_command(event, command, parts):
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
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则，无法确定添加模式。")
            return
        current_rule, _ = rule_info
        is_blacklist = current_rule.add_mode == AddMode.BLACKLIST
    result = await rule_management_service.add_keywords_all_rules(
        keywords=keywords, is_regex=is_regex, is_blacklist=is_blacklist
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
    message_text = event.message.text
    if len(message_text.split(None, 1)) < 2:
        await reply_and_delete(event, "用法: /replace_all <匹配规则> [替换内容]")
        return
    _, args_text = message_text.split(None, 1)
    args_parts = args_text.split(None, 1)
    pattern = args_parts[0]
    content = args_parts[1] if len(args_parts) > 1 else ""
    result = await rule_management_service.add_replace_rules_all_rules(
        patterns=[pattern], replacements=[content], is_regex=True
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
            result = await container.rule_management_service.delete_rule(rule_id)
            if result["success"]:
                success_ids.append(rule_id)
                try:
                    import aiohttp
                    rss_url = f"http://{RSS_HOST}:{RSS_PORT}/api/rule/{rule_id}"
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
        response_parts = []
        if success_ids:
            response_parts.append(f'✅ 成功删除: {", ".join(map(str, success_ids))}')
        if not_found_ids:
            response_parts.append(f'❓ 未找到: {", ".join(map(str, not_found_ids))}')
        if failed_ids:
            response_parts.append(f'❌ 删除失败: {", ".join(map(str, failed_ids))}')
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, "\n".join(response_parts) or "没有规则被删除")
    except Exception as e:
        logger.error(f"删除规则时发生致命错误: {str(e)}")
        await reply_and_delete(event, "删除规则时发生错误，请检查日志")


async def handle_list_rule_command(event, command, parts):
    try:
        try:
            page = int(parts[1]) if len(parts) > 1 else 1
            if page < 1:
                page = 1
        except ValueError:
            await reply_and_delete(event, "页码必须是数字")
            return
        per_page = 30
        rules, total_rules = await container.rule_repo.get_all(page, per_page)
        if not rules:
            await reply_and_delete(event, "当前没有任何转发规则")
            return
        total_pages = (total_rules + per_page - 1) // per_page
        if page > total_pages:
            page = total_pages
            rules, total_rules = await container.rule_repo.get_all(page, per_page)
        message_parts = [f"📋 转发规则列表 (第{page}/{total_pages}页)：\n"]
        for rule in rules:
            source_name = rule.source_chat.name if rule.source_chat else "Unknown"
            source_tid = rule.source_chat.telegram_chat_id if rule.source_chat else "N/A"
            target_name = rule.target_chat.name if rule.target_chat else "Unknown"
            target_tid = rule.target_chat.telegram_chat_id if rule.target_chat else "N/A"
            rule_desc = (
                f"<b>ID: {rule.id}</b>\n"
                f"<blockquote>来源: {source_name} ({source_tid})\n目标: {target_name} ({target_tid})\n</blockquote>"
            )
            message_parts.append(rule_desc)
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
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, "\n".join(message_parts), buttons=buttons, parse_mode="html")
    except Exception as e:
        logger.error(f"列出规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "获取规则列表时发生错误，请检查日志")


async def handle_delete_rss_user_command(event, command, parts):
    from services.user_service import user_service
    try:
        specified_username = parts[1].strip() if len(parts) > 1 else None
        all_users = await user_service.get_all_users()
        if not all_users:
            await reply_and_delete(event, "RSS系统中没有用户账户")
            return
        if specified_username:
            result = await user_service.delete_user_by_username(specified_username)
            if result.get('success'):
                await reply_and_delete(event, f"已删除RSS用户: {specified_username}")
            else:
                await reply_and_delete(event, f"未找到用户名为 '{specified_username}' 的RSS用户")
            return
        if len(all_users) == 1:
            username = all_users[0].username
            result = await user_service.delete_user_by_username(username)
            if result.get('success'):
                await reply_and_delete(event, f"已删除RSS用户: {username}")
            else:
                await reply_and_delete(event, f"删除失败: {result.get('error')}")
            return
        usernames = [u.username for u in all_users]
        user_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(usernames)])
        await reply_and_delete(event, f"请指定要删除的用户名:\n/delete_rss_user <用户名>\n\n现有用户:\n{user_list}")
    except Exception as e:
        logger.error(f"删除RSS用户时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "删除RSS用户失败，请查看日志")
