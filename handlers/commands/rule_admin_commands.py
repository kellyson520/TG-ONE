import os
from core.logging import get_logger
from core.helpers.auto_delete import async_delete_user_message, reply_and_delete, respond_and_delete
from services.rule_management_service import rule_management_service
from services.rule_service import RuleQueryService
from core.constants import TEMP_DIR
from version import VERSION

logger = get_logger(__name__)


async def handle_clear_all_command(event):
    result = await rule_management_service.clear_all_data()
    if result.get('success'):
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, f"✅ {result['message']}")
    else:
        await reply_and_delete(event, f"❌ 清空数据失败: {result.get('error', '未知错误')}")


async def handle_export_keyword_command(event, command):
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            return
        rule, source_chat = rule_info
    lines = await rule_management_service.export_keywords(rule.id)
    if not lines:
        await reply_and_delete(event, "当前规则没有任何关键字")
        return
    from services.rule.facade import rule_management_service as rms
    all_keywords = await rms.get_keywords(rule.id, is_blacklist=None)
    normal_lines = []
    regex_lines = []
    for kw in all_keywords:
        line = f"{kw.keyword} {1 if kw.is_blacklist else 0}"
        if kw.is_regex:
            regex_lines.append(line)
        else:
            normal_lines.append(line)
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
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            return
        rule, source_chat = rule_info
        lines = await rule_management_service.export_replace_rules(rule.id)
        if not lines:
            await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
            await reply_and_delete(event, "当前规则没有任何替换规则")
            return
        replace_file = os.path.join(TEMP_DIR, 'replace_rules.txt')
        with open(replace_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        try:
            await event.client.send_file(event.chat_id, replace_file)
            await respond_and_delete(event, f"规则: {source_chat.name}")
        finally:
            if os.path.exists(replace_file): os.remove(replace_file)


async def handle_import_command(event, command):
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
        from core.helpers.media.excel_importer import parse_excel
        loop = asyncio.get_running_loop()
        try:
            keywords_rows, replacement_rows = await loop.run_in_executor(None, partial(parse_excel, content_bytes))
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
        await reply_and_delete(event, f"类型无效，可选: {', '.join(valid_items)}")
        return
    result = await rule_management_service.update_rule(
        rule_id=rule.id, ufb_domain=domain, ufb_item=item, is_ufb=True
    )
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        await reply_and_delete(event, f"✅ 已绑定 UFB: {domain} ({item})\n源: {source_chat.name}")
    else:
        await reply_and_delete(event, f"❌ UFB绑定失败: {result.get('error')}")


async def handle_ufb_unbind_command(event, command):
    from core.container import container
    async with container.db.get_session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        old_domain = rule.ufb_domain
    result = await rule_management_service.update_rule(
        rule_id=rule.id, ufb_domain=None, ufb_item=None, is_ufb=False
    )
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        await reply_and_delete(event, f'✅ 已解绑 UFB: {old_domain or "无"}')
    else:
        await reply_and_delete(event, f"❌ UFB解绑失败: {result.get('error')}")


async def handle_ufb_item_change_command(event, command):
    from telethon import Button
    from core.container import container
    async with container.db.get_session() as session:
        try:
            from handlers.commands.rule_commands import _get_current_rule_for_chat
            rule_info = await _get_current_rule_for_chat(session, event)
            if not rule_info:
                return
            rule, source_chat = rule_info
            buttons = [
                [Button.inline("主页关键字", "ufb_item:main"), Button.inline("内容页关键字", "ufb_item:content")],
                [Button.inline("主页用户名", "ufb_item:main_username"), Button.inline("内容页用户名", "ufb_item:content_username")],
            ]
            await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
            await reply_and_delete(event, "请选择要切换的UFB同步配置类型:", buttons=buttons)
        except Exception as e:
            await session.rollback()
            logger.error(f"切换UFB配置类型时出错: {str(e)}")
            await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
            await reply_and_delete(event, "切换UFB配置类型时出错，请检查日志")


async def handle_help_command(event, command):
    message_text = (event.message.text or "").strip().lower()
    parts = message_text.split()
    module = parts[1] if len(parts) > 1 else None
    HELP_MODULES = {
        "basic": "**基础命令**\n/start - 开始使用\n/help(/h) [模块] - 显示此帮助信息",
        "bind": "**绑定和设置**\n/bind(/b) <源聊天链接或名称> [目标聊天链接或名称] - 绑定源聊天\n/settings(/s) [规则ID] - 管理转发规则\n/changelog(/cl) - 查看更新日志",
        "rule": "**转发规则管理**\n/copy_rule(/cr)  <源规则ID> [目标规则ID] - 复制指定规则的所有设置到当前规则或目标规则ID\n/list_rule(/lr) - 列出所有转发规则\n/delete_rule(/dr) <规则ID> [规则ID] ... - 删除指定规则",
        "keyword": "**关键字管理**\n/add(/a) <关键字> [关键字] [\"关 键 字\"] ... - 添加普通关键字\n/add_regex(/ar) <正则表达式> ... - 添加正则表达式\n/add_all(/aa) <关键字> ... - 添加普通关键字到当前频道绑定的所有规则\n/add_regex_all(/ara) <正则表达式> ... - 添加正则表达式到所有规则\n/list_keyword(/lk) - 列出所有关键字\n/remove_keyword(/rk) <关键词1> ... - 删除关键字\n/remove_keyword_by_id(/rkbi) <ID> ... - 按ID删除关键字\n/remove_all_keyword(/rak) [关键字] ... - 删除当前频道绑定的所有规则的指定关键字\n/clear_all_keywords(/cak) - 清除当前规则的所有关键字\n/clear_all_keywords_regex(/cakr) - 清除当前规则的所有正则关键字\n/copy_keywords(/ck) <规则ID> - 复制指定规则的关键字到当前规则\n/copy_keywords_regex(/ckr) <规则ID> - 复制指定规则的正则关键字到当前规则",
        "replace": "**替换规则管理**\n/replace(/r) <正则表达式> [替换内容] - 添加替换规则\n/replace_all(/ra) <正则表达式> [替换内容] - 添加替换规则到所有规则\n/list_replace(/lrp) - 列出所有替换规则\n/remove_replace(/rr) <序号> - 删除替换规则\n/clear_all_replace(/car) - 清除当前规则的所有替换规则\n/copy_replace(/crp) <规则ID> - 复制指定规则的替换规则到当前规则",
        "import": "**导入导出**\n/export_keyword(/ek) - 导出当前规则的关键字\n/export_replace(/er) - 导出当前规则的替换规则\n/import_keyword(/ik) <同时发送文件> - 导入普通关键字\n/import_regex_keyword(/irk) <同时发送文件> - 导入正则关键字\n/import_replace(/ir) <同时发送文件> - 导入替换规则\n/import_excel <同时发送xlsx文件> - 一次性导入关键字与替换规则",
        "stats": "**转发记录查询**\n/forward_stats(/fs) [日期] - 查看转发统计 (如: /fs 2024-01-15)\n/forward_search(/fsr) [参数] - 搜索转发记录\n  参数格式: chat:聊天ID user:用户ID type:消息类型 rule:规则ID date:日期 limit:数量\n  例: /fsr chat:-1001234567 type:video limit:5",
        "rss": "**RSS相关**\n/delete_rss_user(/dru) [用户名] - 删除RSS用户",
        "dedup": "**去重相关**\n/dedup - 切换当前规则的去重开关\n/dedup_center(/dc) - 智能去重中心 (GUI 概览)\n/smart_dedup(/sd) - 智能去重高级策略设置\n/clear_dedup_cache(/cdc) - 一键清除去重缓存集\n/dedup_scan - 扫描当前目标会话的重复媒体",
        "db": "**数据库管理**\n/db_info - 查看数据库信息\n/db_backup - 备份数据库\n/db_optimize - 优化数据库\n/db_health - 数据库健康检查",
        "system": "**系统管理**\n/system_status - 查看系统状态\n/admin - 系统管理面板\n/logs - 查看系统日志 (支持 error 参数查看错误日志)\n/download_logs - 下载完整系统日志",
        "ufb": "**UFB相关**\n/ufb_bind(/ub) <域名> - 绑定UFB域名\n/ufb_unbind(/uu) - 解绑UFB域名\n/ufb_item_change(/uic) - 切换UFB同步配置类型",
        "hot": "🔥 **热词分析**\n/hot - 查看全平台热词日报\n/hot <频道名> - 查看指定频道的趋势榜单\n/hot add <词> - 将指定词汇加入垃圾库 (Spam Filter)\n/hot del <词> - 从垃圾库移除指定词汇\n/hot page <页码> - 直接跳转到垃圾库列表指定页\n/hot list - 查看垃圾库词汇列表 (支持分页)\n💡 提示: 垃圾库中的词汇会自动过滤，并且系统也会自动学习发现垃圾特征词。"
    }
    if module and module in HELP_MODULES:
        await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
        await reply_and_delete(event, HELP_MODULES[module], parse_mode="markdown")
        return
    elif module and module not in HELP_MODULES and module != "all":
        valid_modules = ", ".join(HELP_MODULES.keys())
        await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
        await reply_and_delete(event, f"❌ 未知模块: `{module}`\n可选模块: {valid_modules}", parse_mode="markdown")
        return
    header = f"🤖 **Telegram 消息转发机器人 v{VERSION}**\n\n💡 你可以使用 `/help <模块名>` 来查看特定模块的详细指令 (例如: `/help rule`)"
    footer = (
        "💡 **提示**\n"
        "• 括号内为命令的简写形式\n"
        "• 尖括号 <> 表示必填参数\n"
        "• 方括号 [] 表示可选参数\n"
        "• 导入命令需要同时发送文件"
    )
    help_blocks = [header] + list(HELP_MODULES.values()) + [footer]
    full_help_text = "\n\n".join(help_blocks)
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    await reply_and_delete(event, full_help_text, parse_mode="markdown")


async def handle_start_command(event):
    welcome_text = f"""
    👋 欢迎使用 Telegram 消息转发机器人！

    📱 当前版本：v{VERSION}

    📖 查看完整命令列表请使用 /help

    """
    await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
    await reply_and_delete(event, welcome_text)


async def handle_changelog_command(event):
    await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
    from handlers.button.callback.modules.changelog_callback import show_changelog
    await show_changelog(event, page=1)


async def _common_search_handler(event, parts, search_type):
    from handlers.search_ui_manager import SearchUIManager
    from core.helpers.search_system import SearchFilter, get_search_system
    from core.container import container
    if len(parts) < 2:
        await reply_and_delete(event, f"🔍 用法: /{event.message.text.split()[0][1:]} <关键词>")
        return
    query = " ".join(parts[1:])
    search_system = get_search_system(container.user_client)
    filters = SearchFilter(search_type=search_type)
    response = await search_system.search(query, filters, 1)
    message_text = SearchUIManager.generate_search_message(response)
    buttons = SearchUIManager.generate_pagination_buttons(response, "search")
    try:
        await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    except Exception as e:
        logger.warning(f"搜索命令删除用户消息失败: chat_id={getattr(event, 'chat_id', None)}, error={e}")
    await reply_and_delete(event, message_text, buttons=buttons, parse_mode="html")


async def handle_search_command(event, command, parts):
    from core.helpers.search_system import SearchType
    await _common_search_handler(event, parts, SearchType.ALL)


async def handle_search_bound_command(event, command, parts):
    from core.helpers.search_system import SearchType
    await _common_search_handler(event, parts, SearchType.BOUND_CHATS)


async def handle_search_public_command(event, command, parts):
    from core.helpers.search_system import SearchType
    await _common_search_handler(event, parts, SearchType.PUBLIC_CHATS)


async def handle_search_all_command(event, command, parts):
    from core.helpers.search_system import SearchType
    await _common_search_handler(event, parts, SearchType.ALL)
