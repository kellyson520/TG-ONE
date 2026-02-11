import logging
import traceback
from telethon import Button
from sqlalchemy import select
from models.models import Chat, ForwardRule
from core.container import container
from core.helpers.id_utils import find_chat_by_telegram_id_variants
from handlers.list_handlers import show_list

logger = logging.getLogger(__name__)

async def callback_switch(event, rule_id, session, message, data):
    """处理切换源聊天的回调"""
    async with container.db.get_session(session) as s:
        current_chat = await event.get_chat()
        
        # 使用 selectinload 预加载关联以避免 lazy load 错误
        stmt = select(Chat).where(Chat.telegram_chat_id == str(current_chat.id))
        result = await s.execute(stmt)
        current_chat_db = result.scalar_one_or_none()

        if not current_chat_db:
            # 尝试通过 telegram_id_variants 查找 (作为后备)
            current_chat_db = find_chat_by_telegram_id_variants(s, current_chat.id)
            
        if not current_chat_db:
            await event.answer("当前聊天不存在")
            return

        if current_chat_db.current_add_id == rule_id:
            await event.answer("已经选中该聊天")
            return

        current_chat_db.current_add_id = rule_id
        await s.commit()

        rules = await s.execute(
            container.rule_repo.get_rules_for_target_chat(current_chat_db.id)
        )
        rules_list = rules.scalars().all()

        buttons = []
        for rule in rules_list:
            source_chat = rule.source_chat
            current = source_chat.telegram_chat_id == rule_id
            button_text = f'{"✓ " if current else ""}来自: {source_chat.name}'
            callback_data = f"switch:{source_chat.telegram_chat_id}"
            buttons.append([Button.inline(button_text, callback_data)])

        try:
            await message.edit("请选择要管理的转发规则:", buttons=buttons)
        except Exception as e:
            if "message was not modified" not in str(e).lower():
                raise

        source_chat = find_chat_by_telegram_id_variants(s, rule_id)
        await event.answer(f'已切换到: {source_chat.name if source_chat else "未知聊天"}')
    return

async def callback_page(event, rule_id, session, message, data):
    """处理翻页的回调"""
    logger.info(f"翻页回调数据: action=page, rule_id={rule_id}")

    try:
        async with container.db.get_session(session) as s:
            page_number, command = rule_id.split(":")
            page = int(page_number)

            current_chat = await event.get_chat()
            current_chat_db = await s.execute(
                select(Chat).where(Chat.telegram_chat_id == str(current_chat.id))
            )
            current_chat_db = current_chat_db.scalar()

            if not current_chat_db or not current_chat_db.current_add_id:
                await event.answer("请先选择一个源聊天")
                return

            source_chat = find_chat_by_telegram_id_variants(s, current_chat_db.current_add_id)
            rule = await s.get(ForwardRule, 0) # Placeholder for type hint or if needed
            rule_stmt = select(ForwardRule).where(
                ForwardRule.source_chat_id == source_chat.id,
                ForwardRule.target_chat_id == current_chat_db.id
            )
            res = await s.execute(rule_stmt)
            rule = res.scalar()

            if command == "keyword":
                from models.models import Keyword
                keywords = await s.execute(
                     select(Keyword).where(Keyword.rule_id == rule.id)
                )
                keywords = keywords.scalars().all()
                await show_list(event, "keyword", keywords, lambda i, kw: f'{i}. {kw.keyword}{" (正则)" if kw.is_regex else ""}', f"关键字列表\n规则: 来自 {source_chat.name}", page)
            elif command == "replace":
                from models.models import ReplaceRule
                replace_rules = await s.execute(
                    select(ReplaceRule).where(ReplaceRule.rule_id == rule.id)
                )
                replace_rules = replace_rules.scalars().all()
                await show_list(event, "replace", replace_rules, lambda i, rr: f'{i}. 匹配: {rr.pattern} -> {"删除" if not rr.content else f"替换为: {rr.content}"}', f"替换规则列表\n规则: 来自 {source_chat.name}", page)
            await event.answer()
    except Exception as e:
        logger.error(f"处理翻页时出错: {str(e)}")
        await event.answer("处理翻页时出错，请检查日志")
    return

async def callback_toggle_current(event, rule_id, session, message, data):
    """处理切换当前规则的回调"""
    from sqlalchemy.orm import selectinload
    async with container.db.get_session(session) as s:
        # 使用 selectinload 预加载 source_chat 和 target_chat
        stmt = (
            select(ForwardRule)
            .options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat),
                selectinload(ForwardRule.keywords),
                selectinload(ForwardRule.replace_rules),
                selectinload(ForwardRule.media_types),
                selectinload(ForwardRule.media_extensions),
                selectinload(ForwardRule.rss_config),
                selectinload(ForwardRule.push_config),
                selectinload(ForwardRule.rule_syncs),
            )
            .where(ForwardRule.id == int(rule_id))
        )
        result = await s.execute(stmt)
        rule = result.scalar_one_or_none()
        if not rule:
            await event.answer("规则不存在")
            return
        target_chat = rule.target_chat
        source_chat = rule.source_chat
        if target_chat.current_add_id == source_chat.telegram_chat_id:
            await event.answer("已经是当前选中的规则")
            return
        target_chat.current_add_id = source_chat.telegram_chat_id
        await s.commit()
        try:
             # Lazy import to avoid cycle if possible, or assume available
            from handlers.button.settings_manager import create_settings_text, create_buttons
            await message.edit(await create_settings_text(rule), buttons=await create_buttons(rule))
        except Exception as e:
            if "message was not modified" not in str(e).lower():
                raise
        await event.answer(f"已切换到: {source_chat.name}")
    return

async def callback_page_rule(event, page_str, session, message, data):
    """处理规则列表分页的回调"""
    try:
        page = int(page_str)

        async with container.db.get_session(session) as s:
            from sqlalchemy import func
            total_result = await s.execute(select(func.count()).select_from(ForwardRule))
            total_rules = total_result.scalar()
            if total_rules == 0:
                await event.answer("没有任何规则")
                return
            per_page = 30
            total_pages = (total_rules + per_page - 1) // per_page
            offset = (page - 1) * per_page
            
            # Let's use proper ORM with eager load to be safe.
            from sqlalchemy.orm import selectinload
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat)
            ).order_by(ForwardRule.id).offset(offset).limit(per_page)
            
            rules = (await s.execute(stmt)).scalars().all()
            
            message_parts = [f"📋 转发规则列表 (第{page}/{total_pages}页)：\n"]
            for rule in rules:
                rule_desc = f"<b>ID: {rule.id}</b>\n<blockquote>来源: {rule.source_chat.name if rule.source_chat else '未知'}\n目标: {rule.target_chat.name if rule.target_chat else '未知'}</blockquote>"
                message_parts.append(rule_desc)
            
            buttons = []
            nav_row = []
            nav_row.append(Button.inline("⬅️ 上一页" if page > 1 else "⬅️", f"page_rule:{page-1}" if page > 1 else "noop"))
            nav_row.append(Button.inline(f"{page}/{total_pages}", "noop"))
            nav_row.append(Button.inline("下一页 ➡️" if page < total_pages else "➡️", f"page_rule:{page+1}" if page < total_pages else "noop"))
            buttons.append(nav_row)
            await message.edit("\n".join(message_parts), buttons=buttons, parse_mode="html")
    except Exception as e:
        logger.error(f"处理规则列表分页出错: {e}")
        logger.error(f"错误详情: {traceback.format_exc()}")
    return
