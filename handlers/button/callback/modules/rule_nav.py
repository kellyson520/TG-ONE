import logging
import traceback
from telethon import Button
from core.container import container
from handlers.list_handlers import show_list

logger = logging.getLogger(__name__)

async def callback_switch(event, rule_id, session, message, data):
    """处理切换源聊天的回调"""
    try:
        current_chat = await event.get_chat()
        
        # 使用 Repository 层的 DTO 查找
        current_chat_dto = await container.rule_repo.find_chat(current_chat.id)
            
        if not current_chat_dto:
            await event.answer("当前聊天未收录，请先使用 /bind 绑定")
            return

        if current_chat_dto.current_add_id == rule_id:
            await event.answer("已经选中该聊天")
            return

        # 使用 Service 层更新状态
        res = await container.rule_service.set_current_source_chat(current_chat_dto.id, rule_id)
        if not res.get('success'):
            await event.answer(f"❌ 切换失败: {res.get('error')}")
            return

        # 使用 QueryService 获取规则列表刷新 UI
        rules_list = await container.rule_query_service.get_rules_for_target_chat(current_chat_dto.id)

        buttons = []
        for rule in rules_list:
            source_chat = rule.source_chat
            source_telegram_id = source_chat.telegram_chat_id if source_chat else ""
            current = source_telegram_id == rule_id
            source_name = source_chat.name if source_chat else "未知"
            button_text = f'{"✓ " if current else ""}来自: {source_name}'
            callback_data = f"switch:{source_telegram_id}"
            buttons.append([Button.inline(button_text, callback_data)])

        try:
            await message.edit("请选择要管理的转发规则:", buttons=buttons)
        except Exception as e:
            if "message was not modified" not in str(e).lower():
                raise

        # 查找来源聊天名称用于回答提示
        source_chat_dto = await container.rule_repo.find_chat(rule_id)
        await event.answer(f'已切换到: {source_chat_dto.name if source_chat_dto else "未知聊天"}')
    except Exception as e:
        logger.error(f"切换源聊天失败: {e}", exc_info=True)
        await event.answer(f"⚠️ 处理失败: {str(e)}")
    return

async def callback_page(event, rule_id, session, message, data):
    """处理翻页的回调"""
    logger.info(f"翻页回调数据: action=page, rule_id={rule_id}")

    try:
        page_number, command = rule_id.split(":")
        page = int(page_number)

        current_chat = await event.get_chat()
        current_chat_dto = await container.rule_repo.find_chat(current_chat.id)

        if not current_chat_dto or not current_chat_dto.current_add_id:
            await event.answer("请先选择一个源聊天")
            return

        source_chat_dto = await container.rule_repo.find_chat(current_chat_dto.current_add_id)
        if not source_chat_dto:
            await event.answer("管理的来源聊天无效")
            return
            
        rule = await container.rule_repo.get_rule_by_source_target(source_chat_dto.id, current_chat_dto.id)

        if not rule:
            await event.answer("未找到关联规则")
            return

        if command == "keyword":
            # 获取完整规则 DTO (带关键字)
            full_rule = await container.rule_repo.get_by_id(rule.id)
            await show_list(event, "keyword", full_rule.keywords, lambda i, kw: f'{i}. {kw.keyword}{" (正则)" if kw.is_regex else ""}', f"关键字列表\n规则: 来自 {source_chat_dto.name}", page)
        elif command == "replace":
            # 获取完整规则 DTO (带替换规则)
            full_rule = await container.rule_repo.get_by_id(rule.id)
            await show_list(event, "replace", full_rule.replace_rules, lambda i, rr: f'{i}. 匹配: {rr.pattern} -> {"删除" if not rr.content else f"替换为: {rr.content}"}', f"替换规则列表\n规则: 来自 {source_chat_dto.name}", page)
        await event.answer()
    except Exception as e:
        logger.error(f"处理翻页时出错: {str(e)}", exc_info=True)
        await event.answer("⚠️ 翻页失败")
    return

async def callback_toggle_current(event, rule_id, session, message, data):
    """处理切换当前规则的回调"""
    try:
        # 使用 Repository 层的 DTO 获取详情
        rule = await container.rule_repo.get_by_id(int(rule_id))
        
        if not rule:
            await event.answer("规则不存在")
            return
            
        target_chat = rule.target_chat
        source_chat = rule.source_chat
        
        if not target_chat or not source_chat:
            await event.answer("规则信息不完整")
            return

        if target_chat.current_add_id == source_chat.telegram_chat_id:
            await event.answer("已经是当前选中的规则")
            return
            
        # 使用 Service 层设置
        res = await container.rule_service.set_current_source_chat(target_chat.id, source_chat.telegram_chat_id)
        
        if res.get('success'):
            from handlers.button.settings_manager import create_settings_text, create_buttons
            try:
                await message.edit(await create_settings_text(rule), buttons=await create_buttons(rule))
            except Exception as e:
                if "message was not modified" not in str(e).lower():
                    raise
            await event.answer(f"✅ 已切换到: {source_chat.name}")
        else:
            await event.answer(f"❌ 切换失败: {res.get('error')}")
            
    except Exception as e:
        logger.error(f"切换当前规则失败: {e}", exc_info=True)
        await event.answer("⚠️ 切换失败")
    return

async def callback_page_rule(event, page_str, session, message, data):
    """处理规则列表分页的回调"""
    try:
        page = int(page_str)
        # 使用 QueryService 获取所有规则 (此处暂不实现服务端分页，先全量获取再在内存切片以保持兼容)
        all_rules = await container.rule_query_service.get_all_rules_with_chats()
        
        total_rules = len(all_rules)
        if total_rules == 0:
            await event.answer("没有任何规则")
            return
            
        per_page = 30
        total_pages = (total_rules + per_page - 1) // per_page
        offset = (page - 1) * per_page
        rules = all_rules[offset:offset + per_page]
        
        message_parts = [f"📋 转发规则列表 (第{page}/{total_pages}页)：\n"]
        for rule in rules:
            source_name = rule.source_chat.name if rule.source_chat else '未知'
            target_name = rule.target_chat.name if rule.target_chat else '未知'
            rule_desc = f"<b>ID: {rule.id}</b>\n<blockquote>来源: {source_name}\n目标: {target_name}</blockquote>"
            message_parts.append(rule_desc)
        
        buttons = []
        nav_row = []
        nav_row.append(Button.inline("⬅️ 上一页" if page > 1 else "⬅️", f"page_rule:{page-1}" if page > 1 else "noop"))
        nav_row.append(Button.inline(f"{page}/{total_pages}", "noop"))
        nav_row.append(Button.inline("下一页 ➡️" if page < total_pages else "➡️", f"page_rule:{page+1}" if page < total_pages else "noop"))
        buttons.append(nav_row)
        
        await message.edit("\n".join(message_parts), buttons=buttons, parse_mode="html")
    except Exception as e:
        logger.error(f"处理规则列表分页出错: {e}", exc_info=True)
        await event.answer("⚠️ 翻页失败")
    return
