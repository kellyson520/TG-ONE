import traceback

import asyncio
import logging

# aiohttp 在某些环境未安装会导致编辑器波浪线，这里保持局部延迟导入
import os
from sqlalchemy import delete, inspect, select, func
from telethon import Button
from telethon.tl import types

from services.session_service import session_manager
from repositories.db_operations import DBOperations
from models.models import (
    AsyncSessionManager,
    Chat,
    ForwardRule,
    Keyword,
    MediaExtensions,
    MediaTypes,
    ReplaceRule,
    RuleSync,
    get_session,
)
from core.helpers.auto_delete import (
    send_message_and_delete,
)
from core.helpers.common import (
    is_admin,
    check_and_clean_chats,
)
from handlers.button.button_helpers import (
    create_other_settings_buttons,
)
from core.constants import RSS_HOST, RSS_PORT, RULES_PER_PAGE
from core.config import settings
from handlers.button.settings_manager import create_buttons, create_settings_text


logger = logging.getLogger(__name__)


async def handle_other_callback(event):
    """处理通用规则设置回调 (异步版)"""

    data = event.data.decode("utf-8")
    parts = data.split(":")
    action = parts[0]

    # 解析 rule_id
    rule_id = None
    if ":" in data:
        rule_id = parts[1].split(":")[0]  # 获取第一个:后面的内容作为rule_id

    # 特殊操作：关闭设置
    if data == "close_settings":
        await event.delete()
        return

    # 使用 AsyncSessionManager 获取会话
    async with AsyncSessionManager() as session:
        message = await event.get_message()

        # [Refactor Fix] 由于这些处理器定义在 callback_handlers.py 中，需要局部导入以避免循环依赖和 NameError
        from .callback_handlers import (
            callback_toggle_current, callback_switch, callback_settings,
            callback_delete, callback_page, callback_rule_settings,
            callback_set_delay_time, callback_select_delay_time,
            callback_delay_time_page, callback_page_rule, callback_close_settings,
            callback_set_sync_rule, callback_toggle_rule_sync, callback_sync_rule_page,
            callback_set_summary_time, callback_handle_ufb_item
        )

        # 获取对应的处理器
        handler = {
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
            "delete_duplicates": callback_delete_duplicates,
            "view_source_messages": callback_view_source_messages,
            "keep_duplicates": callback_keep_duplicates,
            "confirm_delete_duplicates": callback_confirm_delete_duplicates,
            "toggle_allow_delete_source_on_dedup": callback_toggle_allow_delete_source_on_dedup,
            "ufb_item": callback_handle_ufb_item,
        }.get(action)

        if handler:
            await handler(event, rule_id, session, message, data)


async def _refresh_settings_menu(event, rule):
    """刷新设置菜单"""
    text = await create_settings_text(rule)
    buttons = await create_buttons(rule)
    await event.edit(text, buttons=buttons, parse_mode="markdown")


async def callback_other_settings(event, rule_id, session, message, data):
    await event.edit(
        "其他设置：", buttons=await create_other_settings_buttons(rule_id=rule_id)
    )
    return


async def callback_copy_rule(event, rule_id, session, message, data):
    """显示复制规则选择界面

    选择后将当前规则的设置复制到目标规则。
    """
    try:
        # 检查是否包含page参数
        parts = data.split(":")
        page = 0
        if len(parts) > 2:
            page = int(parts[2])

        # 从rule_id中提取源规则ID
        source_rule_id = rule_id
        if ":" in str(rule_id):
            source_rule_id = str(rule_id).split(":")[0]

        # 创建规则选择按钮
        buttons = await create_copy_rule_buttons(source_rule_id, page)
        await event.edit("请选择要将当前规则复制到的目标规则：", buttons=buttons)
    except Exception as e:
        logger.error(f"显示复制规则选择界面时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer("显示复制规则界面失败")

    return


async def callback_dedup_scan_now(event, rule_id, session, message, data):
    """按钮执行去重扫描"""
    try:
        rule = await session.get(ForwardRule, int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return
        db_ops = await DBOperations.create()
        # 使用用户客户端以避免机器人在频道/部分群历史读取受限
        from core.helpers.common import get_main_module

        main = await get_main_module()
        user_client = main.user_client
        dup_list, dup_map = await db_ops.scan_duplicate_media(
            session, rule.target_chat.telegram_chat_id
        )
        if not dup_list:
            await event.answer("未发现重复媒体")
            return
        # 短报告
        lines = ["发现重复媒体："]
        for sig in dup_list[:10]:
            lines.append(f"- {sig} x{dup_map.get(sig, 2)}")
        if len(dup_list) > 10:
            lines.append(f"... 以及 {len(dup_list) - 10} 项")

        # 创建去重专用按钮（增加删除权限开关入口）
        from telethon import Button

        dedup_buttons = [
            [
                Button.inline("🗑️ 删除重复", f"delete_duplicates:{rule_id}"),
                Button.inline("👀 查看源消息", f"view_source_messages:{rule_id}"),
            ],
            [
                Button.inline(
                    f"🛡️ 删除源消息权限: {'开' if getattr(rule,'allow_delete_source_on_dedup', False) else '关'}",
                    f"toggle_allow_delete_source_on_dedup:{rule_id}",
                )
            ],
            [
                Button.inline("💾 保留", f"keep_duplicates:{rule_id}"),
                Button.inline("👈 返回设置", f"other_settings:{rule_id}"),
            ],
        ]

        # Telethon 要求按钮布局规范，若内容相同的行数可能导致 EditMessage 校验异常
        # 确保 reply_markup 有效：使用新的按钮对象实例
        from telethon import Button as _Btn

        safe_buttons = [
            [
                _Btn.inline("🗑️ 删除重复", f"delete_duplicates:{rule_id}"),
                _Btn.inline("👀 查看源消息", f"view_source_messages:{rule_id}"),
            ],
            [
                _Btn.inline("💾 保留", f"keep_duplicates:{rule_id}"),
                _Btn.inline("👈 返回设置", f"other_settings:{rule_id}"),
            ],
        ]
        await event.edit("\n".join(lines), buttons=safe_buttons)
    except Exception as e:
        logger.error(f"执行去重扫描失败: {str(e)}")
        await event.answer("扫描失败，请检查日志")
    return


async def callback_delete_duplicates(event, rule_id, session, message, data):
    """删除重复媒体"""
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        # 这里可以实现实际的删除逻辑
        # 目前先提示用户
        await event.edit(
            "🗑️ 删除重复媒体功能\n\n"
            "此功能将删除目标聊天中的重复媒体消息。\n"
            "⚠️ 该操作不可撤销，请谨慎操作！\n\n"
            "是否确认删除？",
            buttons=[
                [
                    Button.inline(
                        "✅ 确认删除", f"confirm_delete_duplicates:{rule_id}"
                    ),
                    Button.inline("❌ 取消", f"dedup_scan_now:{rule_id}"),
                ],
                [Button.inline("👈 返回", f"other_settings:{rule_id}")],
            ],
        )
    except Exception as e:
        logger.error(f"处理删除重复请求失败: {str(e)}")
        await event.answer("操作失败，请检查日志")


async def callback_view_source_messages(event, rule_id, session, message, data):
    """查看源消息 (查看已存在的重复消息)"""
    try:
        rule = await session.get(ForwardRule, int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        db_ops = await DBOperations.create()
        # 获取完整记录
        records = await db_ops.get_duplicate_media_records(session, rule.target_chat.telegram_chat_id)
        
        if not records:
            await event.answer("没有找到重复记录")
            return

        text_lines = ["👀 **已存在的重复消息**\n"]
        for r in records:
            # 构建链接
            link = "无链接"
            if r.chat_id and r.message_id:
                # 去除 -100 前缀用于链接
                cid = str(r.chat_id)
                if cid.startswith("-100"):
                    cid = cid[4:]
                link = f"[点击跳转](https://t.me/c/{cid}/{r.message_id})"
            
            type_icon = "📷" if "photo" in r.signature else "📹" if "video" in r.signature else "📁"
            text_lines.append(f"{type_icon} `{r.signature[:8]}...` : {link}")

        text = "\n".join(text_lines)
        
        await event.edit(
            text,
            buttons=[
                [Button.inline("👈 返回", f"dedup_scan_now:{rule_id}")],
                [Button.inline("🏠 返回设置", f"other_settings:{rule_id}")],
            ],
            link_preview=False
        )
    except Exception as e:
        logger.error(f"查看源消息失败: {str(e)}")
        await event.answer("操作失败，请检查日志")


async def callback_keep_duplicates(event, rule_id, session, message, data):
    """保留重复媒体"""
    try:
        await event.edit(
            "💾 已选择保留重复媒体\n\n" "重复媒体将被保留，不做任何删除操作。",
            buttons=[[Button.inline("👈 返回设置", f"other_settings:{rule_id}")]],
        )

        # 3秒后自动返回设置页面
        import asyncio

        await asyncio.sleep(3)
        await callback_other_settings(event, rule_id, session, message, data)

    except Exception as e:
        logger.error(f"处理保留重复请求失败: {str(e)}")
        await event.answer("操作失败，请检查日志")


async def callback_confirm_delete_duplicates(event, rule_id, session, message, data):
    """确认删除重复媒体 (实际执行)"""
    try:
        from models.models import ForwardRule
        from repositories.db_operations import DBOperations
        from core.helpers.common import get_main_module
        from services.media_service import extract_message_signature
        from telethon import Button as _Btn

        rule = await session.get(ForwardRule, int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return
        
        target_chat = rule.target_chat
        if not target_chat:
             await event.answer("目标聊天不存在")
             return

        db_ops = await DBOperations.create()
        # 获取重复签名列表 (count > 1) 
        target_chat_id_str = str(target_chat.telegram_chat_id)
        dup_list, dup_map = await db_ops.scan_duplicate_media(session, target_chat_id_str)

        if not dup_list:
            await event.edit("✅ 未发现重复媒体", buttons=[[_Btn.inline("👈 返回设置", f"other_settings:{rule_id}")]])
            return

        await event.edit(
            f"🗑️ 正在扫描最近1000条消息并删除重复项...\n涉及 {len(dup_list)} 组重复文件\n⚠️ 请勿关闭此窗口，操作正在后台进行...",
            buttons=[]
        )

        main = await get_main_module()
        user_client = main.user_client
        if not user_client:
            await event.edit("❌ 无法获取用户客户端，无法执行删除操作")
            return

        deleted_count = 0
        error_count = 0
        
        # 转换为集合加速查找
        dup_sigs_set = set(dup_list)
        
        # 扫描历史消息 (限制1000条)
        # message_map: signature -> list of Msg
        message_map = {}
        
        try:
            # 获取 entity
            try:
                entity = await user_client.get_entity(int(target_chat_id_str))
            except:
                # 尝试用 username
                if target_chat.username:
                    entity = await user_client.get_entity(target_chat.username)
                else:
                    raise ValueError(f"无法获取聊天实体: {target_chat.name}")

            async for msg in user_client.iter_messages(entity, limit=1000):
                if not msg.media:
                    continue
                
                sig, fid = extract_message_signature(msg)
                
                # 检查三种可能的签名格式 (sig, fid:xxx, document:xxx)
                sig_key = None
                
                if fid and f"fid:{fid}" in dup_sigs_set:
                    sig_key = f"fid:{fid}"
                elif sig and sig in dup_sigs_set:
                    sig_key = sig
                    
                if sig_key:
                    if sig_key not in message_map:
                        message_map[sig_key] = []
                    message_map[sig_key].append(msg)

        except Exception as e:
             logger.error(f"扫描历史消息失败: {str(e)}", exc_info=True)
             await event.edit(f"❌ 扫描消息历史时失败: {str(e)}", buttons=[[_Btn.inline("👈 返回", f"other_settings:{rule_id}")]])
             return

        # 执行删除
        if not message_map:
             await event.edit("⚠️ 数据库显示有重复，但在最近 1000 条消息中未找到匹配的媒体文件。\n建议手动检查或扫描更多历史。", buttons=[[_Btn.inline("👈 返回", f"other_settings:{rule_id}")]])
             return

        for sig, msgs in message_map.items():
            if len(msgs) > 1:
                # 按日期排序 (旧 -> 新)
                msgs.sort(key=lambda x: x.date)
                
                # 保留第一个 (最旧的)，删除其余的
                to_delete = msgs[1:]
                to_delete_ids = [m.id for m in to_delete]
                
                try:
                    await user_client.delete_messages(entity, to_delete_ids)
                    deleted_count += len(to_delete)
                    logger.info(f"已删除 {len(to_delete)} 条重复消息 (签名: {sig})")
                except Exception as e:
                    error_count += len(to_delete)
                    logger.error(f"删除消息失败: {str(e)}")
        
        result_text = (
            f"✅ 操作完成\n\n"
            f"🗑️ 已删除消息: {deleted_count} 条\n"
            f"⚠️ 删除失败: {error_count} 条\n"
            f"ℹ️ 已保留每组中最旧的一条消息"
        )
        
        await event.edit(
            result_text,
            buttons=[[_Btn.inline("👈 返回设置", f"other_settings:{rule_id}")]]
        )

    except Exception as e:
        logger.error(f"删除重复媒体失败: {str(e)}", exc_info=True)
        await event.answer("删除失败，请检查日志")


async def callback_handle_ufb_item(event, rule_id, session, message, data):
    """处理 UFB Item 切换回调
    data 格式: ufb_item:type (例如 ufb_item:main)
    注意: 这里的 rule_id 参数是从 data 解析的，实际上是 item_type，不是真正的 rule_id
    """
    try:
        parts = data.split(":")
        if len(parts) < 2:
            await event.answer("参数错误")
            return
            
        item_type = parts[1]
        
        # 必须根据上下文查找当前规则
        current_chat = await event.get_chat()
        from models.models import ForwardRule
        from sqlalchemy import select
        
        stmt = select(Chat).where(Chat.telegram_chat_id == str(current_chat.id))
        result = await session.execute(stmt)
        chat = result.scalar_one_or_none()
        
        if not chat or not chat.current_add_id:
            await event.answer("未找到当前规则上下文")
            return
            
        # 查找规则 (通过 current_add_id 作为 source_chat_telegram_id)
        from core.helpers.id_utils import find_chat_by_telegram_id_variants
        source_chat = find_chat_by_telegram_id_variants(session, chat.current_add_id)
        if not source_chat:
            await event.answer("源聊天不存在")
            return
            
        stmt = select(ForwardRule).where(
            ForwardRule.source_chat_id == source_chat.id,
            ForwardRule.target_chat_id == chat.id
        )
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        
        if not rule:
            await event.answer("规则不存在")
            return
            
        # 更新设置
        rule.ufb_item = item_type
        await session.commit()
        
        await event.answer(f"✅ 已切换 UFB 绑定类型为: {item_type}")
        # 还可以更新消息显示当前选中的类型，但这里作为简单响应即可
        
    except Exception as e:
        logger.error(f"处理UFB Item回调失败: {str(e)}", exc_info=True)
        await event.answer("操作失败")


async def callback_toggle_allow_delete_source_on_dedup(
    event, rule_id, session, message, data
):
    """切换是否允许删除源群消息权限设置"""
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return
        current = getattr(rule, "allow_delete_source_on_dedup", False)
        rule.allow_delete_source_on_dedup = not current
        await session.commit()
        await event.answer(
            f"已设置: 删除源消息权限 = {'开' if rule.allow_delete_source_on_dedup else '关'}"
        )
        # 返回上一页
        await callback_dedup_scan_now(event, rule_id, session, message, data)
    except Exception as e:
        logger.error(f"切换删除源消息权限失败: {str(e)}")
        await event.answer("操作失败，请检查日志")


async def create_copy_rule_buttons(rule_id, page=0):
    """创建复制规则按钮列表

    Args:
        rule_id: 当前规则ID
        page: 当前页码

    Returns:
        按钮列表
    """
    # 设置分页参数

    buttons = []
    session = get_session()

    try:
        # 获取当前规则
        if ":" in str(rule_id):
            parts = str(rule_id).split(":")
            source_rule_id = int(parts[0])
        else:
            source_rule_id = int(rule_id)

        current_rule = session.query(ForwardRule).get(source_rule_id)
        if not current_rule:
            buttons.append([Button.inline("❌ 规则不存在", "noop")])
            buttons.append([Button.inline("关闭", "close_settings")])
            return buttons

        # 获取所有规则（除了当前规则）
        all_rules = (
            session.query(ForwardRule).filter(ForwardRule.id != source_rule_id).all()
        )

        # 计算分页
        total_rules = len(all_rules)
        total_pages = (total_rules + RULES_PER_PAGE - 1) // RULES_PER_PAGE

        if total_rules == 0:
            buttons.append(
                [
                    Button.inline("👈 返回", f"other_settings:{source_rule_id}"),
                    Button.inline("❌ 关闭", "close_settings"),
                ]
            )
            return buttons

        # 获取当前页的规则
        start_idx = page * RULES_PER_PAGE
        end_idx = min(start_idx + RULES_PER_PAGE, total_rules)
        current_page_rules = all_rules[start_idx:end_idx]

        # 创建规则按钮
        for rule in current_page_rules:
            # 获取源聊天和目标聊天名称
            source_chat = rule.source_chat
            target_chat = rule.target_chat

            # 创建按钮文本
            button_text = f"{rule.id} {source_chat.name}->{target_chat.name}"

            # 创建回调数据：perform_copy_rule:源规则ID:目标规则ID
            callback_data = f"perform_copy_rule:{source_rule_id}:{rule.id}"

            buttons.append([Button.inline(button_text, callback_data)])

        # 添加分页按钮
        page_buttons = []

        if total_pages > 1:
            # 上一页按钮
            if page > 0:
                page_buttons.append(
                    Button.inline("⬅️", f"copy_rule:{source_rule_id}:{page-1}")
                )
            else:
                page_buttons.append(Button.inline("⬅️", f"noop"))

            # 页码指示
            page_buttons.append(Button.inline(f"{page+1}/{total_pages}", f"noop"))

            # 下一页按钮
            if page < total_pages - 1:
                page_buttons.append(
                    Button.inline("➡️", f"copy_rule:{source_rule_id}:{page+1}")
                )
            else:
                page_buttons.append(Button.inline("➡️", f"noop"))

        if page_buttons:
            buttons.append(page_buttons)

        buttons.append(
            [
                Button.inline("👈 返回", f"other_settings:{source_rule_id}"),
                Button.inline("❌ 关闭", "close_settings"),
            ]
        )

    finally:
        session.close()

    return buttons


async def callback_perform_copy_rule(event, rule_id_data, session, message, data):
    """执行复制规则操作

    Args:
        rule_id_data: 格式为 "源规则ID:目标规则ID"
    """
    try:
        # 解析规则ID
        parts = rule_id_data.split(":")
        if len(parts) != 2:
            await event.answer("数据格式错误")
            return

        source_rule_id = int(parts[0])
        target_rule_id = int(parts[1])

        # 获取源规则和目标规则
        source_rule = await session.get(ForwardRule, source_rule_id)
        target_rule = await session.get(ForwardRule, target_rule_id)

        if not source_rule or not target_rule:
            await event.answer("源规则或目标规则不存在")
            return

        if source_rule.id == target_rule.id:
            await event.answer("不能复制规则到自身")
            return

        # 记录复制的各个部分成功数量
        keywords_normal_success = 0
        keywords_normal_skip = 0
        keywords_regex_success = 0
        keywords_regex_skip = 0
        replace_rules_success = 0
        replace_rules_skip = 0
        media_extensions_success = 0
        media_extensions_skip = 0
        rule_syncs_success = 0
        rule_syncs_skip = 0

        # 复制普通关键字
        for keyword in source_rule.keywords:
            if not keyword.is_regex:  # 普通关键字
                # 检查是否已存在
                exists = any(
                    not k.is_regex
                    and k.keyword == keyword.keyword
                    and k.is_blacklist == keyword.is_blacklist
                    for k in target_rule.keywords
                )
                if not exists:
                    new_keyword = Keyword(
                        rule_id=target_rule.id,
                        keyword=keyword.keyword,
                        is_regex=False,
                        is_blacklist=keyword.is_blacklist,
                    )
                    session.add(new_keyword)
                    keywords_normal_success += 1
                else:
                    keywords_normal_skip += 1

        # 复制正则关键字
        for keyword in source_rule.keywords:
            if keyword.is_regex:  # 正则关键字
                # 检查是否已存在
                exists = any(
                    k.is_regex
                    and k.keyword == keyword.keyword
                    and k.is_blacklist == keyword.is_blacklist
                    for k in target_rule.keywords
                )
                if not exists:
                    new_keyword = Keyword(
                        rule_id=target_rule.id,
                        keyword=keyword.keyword,
                        is_regex=True,
                        is_blacklist=keyword.is_blacklist,
                    )
                    session.add(new_keyword)
                    keywords_regex_success += 1
                else:
                    keywords_regex_skip += 1

        # 复制替换规则
        for replace_rule in source_rule.replace_rules:
            # 检查是否已存在
            exists = any(
                r.pattern == replace_rule.pattern and r.content == replace_rule.content
                for r in target_rule.replace_rules
            )
            if not exists:
                new_rule = ReplaceRule(
                    rule_id=target_rule.id,
                    pattern=replace_rule.pattern,
                    content=replace_rule.content,
                )
                session.add(new_rule)
                replace_rules_success += 1
            else:
                replace_rules_skip += 1

        # 复制媒体扩展名设置
        if hasattr(source_rule, "media_extensions") and source_rule.media_extensions:
            for extension in source_rule.media_extensions:
                # 检查是否已存在
                exists = any(
                    e.extension == extension.extension
                    for e in target_rule.media_extensions
                )
                if not exists:
                    new_extension = MediaExtensions(
                        rule_id=target_rule.id, extension=extension.extension
                    )
                    session.add(new_extension)
                    media_extensions_success += 1
                else:
                    media_extensions_skip += 1

        # 复制媒体类型设置
        if hasattr(source_rule, "media_types") and source_rule.media_types:
            target_media_types = (
                session.query(MediaTypes).filter_by(rule_id=target_rule.id).first()
            )

            if not target_media_types:
                # 如果目标规则没有媒体类型设置，创建新的
                target_media_types = MediaTypes(rule_id=target_rule.id)

                # 使用inspect自动复制所有字段（除了id和rule_id）
                media_inspector = inspect(MediaTypes)
                for column in media_inspector.columns:
                    column_name = column.key
                    if column_name not in ["id", "rule_id"]:
                        setattr(
                            target_media_types,
                            column_name,
                            getattr(source_rule.media_types, column_name),
                        )

                session.add(target_media_types)
            else:
                # 如果已有设置，更新现有设置
                # 使用inspect自动复制所有字段（除了id和rule_id）
                media_inspector = inspect(MediaTypes)
                for column in media_inspector.columns:
                    column_name = column.key
                    if column_name not in ["id", "rule_id"]:
                        setattr(
                            target_media_types,
                            column_name,
                            getattr(source_rule.media_types, column_name),
                        )

        # 复制规则同步表数据
        # 检查源规则是否有同步关系
        if hasattr(source_rule, "rule_syncs") and source_rule.rule_syncs:
            for sync in source_rule.rule_syncs:
                # 检查是否已存在
                exists = any(
                    s.sync_rule_id == sync.sync_rule_id for s in target_rule.rule_syncs
                )
                if not exists:
                    # 确保不会创建自引用的同步关系
                    if sync.sync_rule_id != target_rule.id:
                        new_sync = RuleSync(
                            rule_id=target_rule.id, sync_rule_id=sync.sync_rule_id
                        )
                        session.add(new_sync)
                        rule_syncs_success += 1

                        # 启用目标规则的同步功能
                        if rule_syncs_success > 0:
                            target_rule.enable_sync = True
                else:
                    rule_syncs_skip += 1

        # 复制规则设置
        # 保存目标规则的原始关联
        original_source_chat_id = target_rule.source_chat_id
        original_target_chat_id = target_rule.target_chat_id

        # 获取ForwardRule模型的所有字段
        inspector = inspect(ForwardRule)
        for column in inspector.columns:
            column_name = column.key
            if column_name not in [
                "id",
                "source_chat_id",
                "target_chat_id",
                "source_chat",
                "target_chat",
                "keywords",
                "replace_rules",
                "media_types",
            ]:
                # 获取源规则的值并设置到目标规则
                value = getattr(source_rule, column_name)
                setattr(target_rule, column_name, value)

        # 恢复目标规则的原始关联
        target_rule.source_chat_id = original_source_chat_id
        target_rule.target_chat_id = original_target_chat_id

        # 保存更改
        await session.commit()

        # 构建消息内容
        result_message = (
            f"✅ 已从规则 `{source_rule_id}` 复制到规则 `{target_rule.id}`\n\n"
            f"普通关键字: 成功复制 {keywords_normal_success} 个, 跳过重复 {keywords_normal_skip} 个\n"
            f"正则关键字: 成功复制 {keywords_regex_success} 个, 跳过重复 {keywords_regex_skip} 个\n"
            f"替换规则: 成功复制 {replace_rules_success} 个, 跳过重复 {replace_rules_skip} 个\n"
            f"媒体扩展名: 成功复制 {media_extensions_success} 个, 跳过重复 {media_extensions_skip} 个\n"
            f"同步规则: 成功复制 {rule_syncs_success} 个, 跳过重复 {rule_syncs_skip} 个\n"
            f"媒体类型设置和其他规则设置已复制\n"
        )

        # 创建返回设置按钮
        buttons = [
            [
                Button.inline("👈 返回设置", f"other_settings:{source_rule.id}"),
                Button.inline("❌ 关闭", "close_settings"),
            ]
        ]

        # 删除原消息
        await message.delete()

        # 发送新消息
        await send_message_and_delete(
            event.client,
            event.chat_id,
            result_message,
            buttons=buttons,
            parse_mode="markdown",
        )

        await event.answer(
            f"已从规则 {source_rule_id} 复制所有设置到规则 {target_rule_id}"
        )

    except Exception as e:
        logger.error(f"复制规则时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"复制规则失败: {str(e)}")
    return


async def callback_copy_keyword(event, rule_id, session, message, data):
    """复制关键字

    显示可选择的规则列表，供用户选择要复制关键字到的目标规则。
    选择后将当前规则的关键字复制到目标规则。
    """
    try:
        # 调用通用的规则选择函数
        await show_rule_selection(
            event,
            rule_id,
            data,
            "请选择要将当前规则的关键字复制到的目标规则：",
            "perform_copy_keyword",
        )
    except Exception as e:
        logger.error(f"显示复制关键字选择界面时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer("显示复制关键字界面失败")
    return


async def callback_copy_replace(event, rule_id, session, message, data):
    """复制替换规则

    显示可选择的规则列表，供用户选择要复制替换规则到的目标规则。
    选择后将当前规则的替换规则复制到目标规则。
    """
    try:
        # 调用通用的规则选择函数
        await show_rule_selection(
            event,
            rule_id,
            data,
            "请选择要将当前规则的替换规则复制到的目标规则：",
            "perform_copy_replace",
        )
    except Exception as e:
        logger.error(f"显示复制替换规则选择界面时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer("显示复制替换规则界面失败")
    return


async def callback_perform_copy_keyword(event, rule_id_data, session, message, data):
    """执行复制关键字操作

    Args:
        rule_id_data: 格式为 "源规则ID:目标规则ID"
    """
    try:
        # 解析规则ID
        source_rule_id, target_rule_id = await parse_rule_ids(event, rule_id_data)
        if source_rule_id is None or target_rule_id is None:
            return

        # 获取源规则和目标规则
        source_rule, target_rule = await get_rules(
            event, session, source_rule_id, target_rule_id
        )
        if not source_rule or not target_rule:
            return

        # 记录复制的各个部分成功数量
        keywords_normal_success = 0
        keywords_normal_skip = 0
        keywords_regex_success = 0
        keywords_regex_skip = 0

        # 复制普通关键字
        for keyword in source_rule.keywords:
            if not keyword.is_regex:  # 普通关键字
                # 检查是否已存在
                exists = any(
                    not k.is_regex
                    and k.keyword == keyword.keyword
                    and k.is_blacklist == keyword.is_blacklist
                    for k in target_rule.keywords
                )
                if not exists:
                    new_keyword = Keyword(
                        rule_id=target_rule.id,
                        keyword=keyword.keyword,
                        is_regex=False,
                        is_blacklist=keyword.is_blacklist,
                    )
                    session.add(new_keyword)
                    keywords_normal_success += 1
                else:
                    keywords_normal_skip += 1

        # 复制正则关键字
        for keyword in source_rule.keywords:
            if keyword.is_regex:  # 正则关键字
                # 检查是否已存在
                exists = any(
                    k.is_regex
                    and k.keyword == keyword.keyword
                    and k.is_blacklist == keyword.is_blacklist
                    for k in target_rule.keywords
                )
                if not exists:
                    new_keyword = Keyword(
                        rule_id=target_rule.id,
                        keyword=keyword.keyword,
                        is_regex=True,
                        is_blacklist=keyword.is_blacklist,
                    )
                    session.add(new_keyword)
                    keywords_regex_success += 1
                else:
                    keywords_regex_skip += 1

        # 保存更改
        session.commit()

        # 构建消息内容
        result_message = (
            f"✅ 已从规则 `{source_rule_id}` 复制关键字到规则 `{target_rule.id}`\n\n"
            f"普通关键字: 成功复制 {keywords_normal_success} 个, 跳过重复 {keywords_normal_skip} 个\n"
            f"正则关键字: 成功复制 {keywords_regex_success} 个, 跳过重复 {keywords_regex_skip} 个\n"
        )

        # 发送结果消息
        await send_result_message(event, message, result_message, source_rule.id)

        await event.answer(
            f"已从规则 {source_rule_id} 复制关键字到规则 {target_rule_id}"
        )

    except Exception as e:
        logger.error(f"复制关键字时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"复制关键字失败: {str(e)}")
    return


async def callback_perform_copy_replace(event, rule_id_data, session, message, data):
    """执行复制替换规则操作

    Args:
        rule_id_data: 格式为 "源规则ID:目标规则ID"
    """
    try:
        # 解析规则ID
        source_rule_id, target_rule_id = await parse_rule_ids(event, rule_id_data)
        if source_rule_id is None or target_rule_id is None:
            return

        # 获取源规则和目标规则
        source_rule, target_rule = await get_rules(
            event, session, source_rule_id, target_rule_id
        )
        if not source_rule or not target_rule:
            return

        # 记录复制的成功数量
        replace_rules_success = 0
        replace_rules_skip = 0

        # 复制替换规则
        for replace_rule in source_rule.replace_rules:
            # 检查是否已存在
            exists = any(
                r.pattern == replace_rule.pattern and r.content == replace_rule.content
                for r in target_rule.replace_rules
            )
            if not exists:
                new_rule = ReplaceRule(
                    rule_id=target_rule.id,
                    pattern=replace_rule.pattern,
                    content=replace_rule.content,
                )
                session.add(new_rule)
                replace_rules_success += 1
            else:
                replace_rules_skip += 1

        # 保存更改
        session.commit()

        # 构建消息内容
        result_message = (
            f"✅ 已从规则 `{source_rule_id}` 复制替换规则到规则 `{target_rule.id}`\n\n"
            f"替换规则: 成功复制 {replace_rules_success} 个, 跳过重复 {replace_rules_skip} 个\n"
        )

        # 发送结果消息
        await send_result_message(event, message, result_message, source_rule.id)

        await event.answer(
            f"已从规则 {source_rule_id} 复制替换规则到规则 {target_rule_id}"
        )

    except Exception as e:
        logger.error(f"复制替换规则时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"复制替换规则失败: {str(e)}")
    return


# 通用辅助函数
async def show_rule_selection(event, rule_id, data, title, callback_action):
    """显示规则选择界面的通用函数

    Args:
        event: 事件对象
        rule_id: 当前规则ID
        data: 回调数据
        title: 显示标题
        callback_action: 选择后要执行的回调动作
    """
    # 检查是否包含page参数
    parts = data.split(":")
    page = 0
    if len(parts) > 2:
        page = int(parts[2])

    # 从rule_id中提取源规则ID
    source_rule_id = rule_id
    if ":" in str(rule_id):
        source_rule_id = str(rule_id).split(":")[0]

    # 创建规则选择按钮
    buttons = await create_rule_selection_buttons(source_rule_id, page, callback_action)
    await event.edit(title, buttons=buttons)


async def create_rule_selection_buttons(
    rule_id, page=0, callback_action="perform_copy_rule"
):
    """创建规则选择按钮的通用函数

    Args:
        rule_id: 当前规则ID
        page: 当前页码
        callback_action: 按钮点击后的回调动作

    Returns:
        按钮列表
    """
    # 设置分页参数

    buttons = []
    session = get_session()

    try:
        # 获取当前规则
        if ":" in str(rule_id):
            parts = str(rule_id).split(":")
            source_rule_id = int(parts[0])
        else:
            source_rule_id = int(rule_id)

        current_rule = session.query(ForwardRule).get(source_rule_id)
        if not current_rule:
            buttons.append([Button.inline("❌ 规则不存在", "noop")])
            buttons.append([Button.inline("关闭", "close_settings")])
            return buttons

        # 获取所有规则（除了当前规则）
        all_rules = (
            session.query(ForwardRule).filter(ForwardRule.id != source_rule_id).all()
        )

        # 计算分页
        total_rules = len(all_rules)
        total_pages = (total_rules + RULES_PER_PAGE - 1) // RULES_PER_PAGE

        if total_rules == 0:
            # buttons.append([Button.inline('❌ 没有可用的规则', 'noop')])
            buttons.append(
                [
                    Button.inline("👈 返回", f"other_settings:{source_rule_id}"),
                    Button.inline("❌ 关闭", "close_settings"),
                ]
            )
            return buttons

        # 获取当前页的规则
        start_idx = page * RULES_PER_PAGE
        end_idx = min(start_idx + RULES_PER_PAGE, total_rules)
        current_page_rules = all_rules[start_idx:end_idx]

        # 创建规则按钮
        for rule in current_page_rules:
            # 获取源聊天和目标聊天名称
            source_chat = rule.source_chat
            target_chat = rule.target_chat

            # 创建按钮文本
            button_text = f"{rule.id} {source_chat.name}->{target_chat.name}"

            # 创建回调数据：callback_action:源规则ID:目标规则ID
            callback_data = f"{callback_action}:{source_rule_id}:{rule.id}"

            buttons.append([Button.inline(button_text, callback_data)])

        # 添加分页按钮
        page_buttons = []
        action_name = callback_action.replace("perform_", "")

        if total_pages > 1:
            # 上一页按钮
            if page > 0:
                page_buttons.append(
                    Button.inline("⬅️", f"{action_name}:{source_rule_id}:{page-1}")
                )
            else:
                page_buttons.append(Button.inline("⬅️", f"noop"))

            # 页码指示
            page_buttons.append(Button.inline(f"{page+1}/{total_pages}", f"noop"))

            # 下一页按钮
            if page < total_pages - 1:
                page_buttons.append(
                    Button.inline("➡️", f"{action_name}:{source_rule_id}:{page+1}")
                )
            else:
                page_buttons.append(Button.inline("➡️", f"noop"))

        if page_buttons:
            buttons.append(page_buttons)

        buttons.append(
            [
                Button.inline("👈 返回", f"other_settings:{source_rule_id}"),
                Button.inline("❌ 关闭", "close_settings"),
            ]
        )

    finally:
        session.close()

    return buttons


async def parse_rule_ids(event, rule_id_data):
    """解析规则ID

    Args:
        event: 事件对象
        rule_id_data: 格式为 "源规则ID:目标规则ID"

    Returns:
        (source_rule_id, target_rule_id) 或 (None, None)
    """
    parts = rule_id_data.split(":")
    if len(parts) != 2:
        await event.answer("数据格式错误")
        return None, None

    source_rule_id = int(parts[0])
    target_rule_id = int(parts[1])

    if source_rule_id == target_rule_id:
        await event.answer("不能复制到自身")
        return None, None

    return source_rule_id, target_rule_id


async def get_rules(event, session, source_rule_id, target_rule_id):
    """获取源规则和目标规则

    Args:
        event: 事件对象
        session: 数据库会话
        source_rule_id: 源规则ID
        target_rule_id: 目标规则ID

    Returns:
        (source_rule, target_rule) 或 (None, None)
    """
    source_rule = await session.get(ForwardRule, source_rule_id)
    target_rule = await session.get(ForwardRule, target_rule_id)

    if not source_rule or not target_rule:
        await event.answer("源规则或目标规则不存在")
        return None, None

    return source_rule, target_rule


async def send_result_message(event, message, result_message, target_rule_id):
    """发送结果消息

    Args:
        event: 事件对象
        message: 原消息对象
        result_message: 结果消息内容
        target_rule_id: 目标规则ID
    """
    # 创建返回设置按钮
    buttons = [
        [
            Button.inline("👈 返回设置", f"other_settings:{target_rule_id}"),
            Button.inline("❌ 关闭", "close_settings"),
        ]
    ]

    # 删除原消息
    await message.delete()

    # 发送新消息
    await send_message_and_delete(
        event.client,
        event.chat_id,
        result_message,
        buttons=buttons,
        parse_mode="markdown",
    )


async def callback_clear_keyword(event, rule_id, session, message, data):
    """显示清空关键字规则选择界面"""
    try:
        # 检查是否包含page参数
        parts = data.split(":")
        page = 0
        if len(parts) > 2:
            page = int(parts[2])

        # 获取规则信息
        current_rule = session.query(ForwardRule).get(int(rule_id))
        if not current_rule:
            await event.answer("规则不存在")
            return

        # 创建按钮列表，首先添加当前规则
        buttons = []
        source_chat = current_rule.source_chat
        target_chat = current_rule.target_chat

        # 当前规则按钮
        current_button_text = f"🗑️ 清空当前规则"
        current_callback_data = f"perform_clear_keyword:{current_rule.id}"
        buttons.append([Button.inline(current_button_text, current_callback_data)])

        # 检查是否有其他规则

        result = await session.execute(
            select(func.count(ForwardRule.id)).filter(ForwardRule.id != current_rule.id)
        )
        other_rules = result.scalar()

        if other_rules > 0:
            # 分隔符
            buttons.append([Button.inline("---------", "noop")])

            # 添加其他规则按钮
            other_buttons = await create_rule_selection_buttons(
                rule_id, page, "perform_clear_keyword"
            )

            # 将所有其他规则按钮添加到buttons中
            buttons.extend(other_buttons)
        else:
            # 添加返回和关闭按钮
            buttons.append(
                [
                    Button.inline("👈 返回", f"other_settings:{current_rule.id}"),
                    Button.inline("❌ 关闭", "close_settings"),
                ]
            )

        await event.edit("请选择要清空关键字的规则：", buttons=buttons)
    except Exception as e:
        logger.error(f"显示清空关键字选择界面时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer("显示清空关键字界面失败")
    return


async def callback_clear_replace(event, rule_id, session, message, data):
    """显示清空替换规则选择界面"""
    try:
        # 检查是否包含page参数
        parts = data.split(":")
        page = 0
        if len(parts) > 2:
            page = int(parts[2])

        # 获取规则信息
        current_rule = session.query(ForwardRule).get(int(rule_id))
        if not current_rule:
            await event.answer("规则不存在")
            return

        # 创建按钮列表，首先添加当前规则
        buttons = []
        source_chat = current_rule.source_chat
        target_chat = current_rule.target_chat

        # 当前规则按钮
        current_button_text = f"🗑️ 清空当前规则"
        current_callback_data = f"perform_clear_replace:{current_rule.id}"
        buttons.append([Button.inline(current_button_text, current_callback_data)])

        # 检查是否有其他规则
        other_rules = (
            session.query(ForwardRule).filter(ForwardRule.id != current_rule.id).count()
        )

        if other_rules > 0:
            # 分隔符
            buttons.append([Button.inline("---------", "noop")])

            # 添加其他规则按钮
            other_buttons = await create_rule_selection_buttons(
                rule_id, page, "perform_clear_replace"
            )

            # 将所有其他规则按钮添加到buttons中
            buttons.extend(other_buttons)
        else:
            # 添加返回和关闭按钮
            buttons.append(
                [
                    Button.inline("👈 返回", f"other_settings:{current_rule.id}"),
                    Button.inline("❌ 关闭", "close_settings"),
                ]
            )

        await event.edit("请选择要清空替换规则的规则：", buttons=buttons)
    except Exception as e:
        logger.error(f"显示清空替换规则选择界面时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer("显示清空替换规则界面失败")
    return


async def callback_delete_rule(event, rule_id, session, message, data):
    """显示删除规则选择界面"""
    try:
        # 检查是否包含page参数
        parts = data.split(":")
        page = 0
        if len(parts) > 2:
            page = int(parts[2])

        source_rule_id = rule_id
        if ":" in str(rule_id):
            source_rule_id = str(rule_id).split(":")[0]

        # 获取规则信息
        current_rule = session.query(ForwardRule).get(int(source_rule_id))
        if not current_rule:
            await event.answer("规则不存在")
            return

        # 创建按钮列表，首先添加当前规则
        buttons = []
        source_chat = current_rule.source_chat
        target_chat = current_rule.target_chat

        # 当前规则按钮
        current_button_text = f"❌ 删除当前规则"
        current_callback_data = f"perform_delete_rule:{current_rule.id}"
        buttons.append([Button.inline(current_button_text, current_callback_data)])

        # 检查是否有其他规则
        other_rules = (
            session.query(ForwardRule).filter(ForwardRule.id != current_rule.id).count()
        )

        if other_rules > 0:
            # 分隔符
            buttons.append([Button.inline("---------", "noop")])

            # 添加其他规则按钮
            other_buttons = await create_rule_selection_buttons(
                rule_id, page, "perform_delete_rule"
            )

            # 将所有其他规则按钮添加到buttons中
            buttons.extend(other_buttons)
        else:
            # 添加返回和关闭按钮
            buttons.append(
                [
                    Button.inline("👈 返回", f"other_settings:{current_rule.id}"),
                    Button.inline("❌ 关闭", "close_settings"),
                ]
            )

        await event.edit("请选择要删除的规则：", buttons=buttons)
    except Exception as e:
        logger.error(f"显示删除规则选择界面时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer("显示删除规则界面失败")
    return


# 执行清空关键字的回调
async def callback_perform_clear_keyword(event, rule_id_data, session, message, data):
    """执行清空关键字操作"""
    try:
        # 检查是否包含多个规则ID（格式为source_id:target_id）
        if ":" in rule_id_data:
            # 解析规则ID
            source_rule_id, target_rule_id = await parse_rule_ids(event, rule_id_data)
            if source_rule_id is None or target_rule_id is None:
                return

            # 使用目标规则ID
            rule_id = target_rule_id
        else:
            # 单个规则ID的情况（当前规则）
            rule_id = int(rule_id_data)

        # 获取规则
        rule = session.query(ForwardRule).get(rule_id)
        if not rule:
            await event.answer("规则不存在")
            return

        # 获取并删除所有关键字
        keyword_count = len(rule.keywords)

        # 删除所有关键字
        await session.execute(delete(Keyword).filter(Keyword.rule_id == rule.id))
        await session.commit()

        # 构建消息内容
        result_message = (
            f"✅ 已清空规则 `{rule.id}` 的所有关键字，共删除 {keyword_count} 个关键字"
        )

        # 返回按钮指向源规则的设置页面（如果有的话）
        source_id = int(rule_id_data.split(":")[0]) if ":" in rule_id_data else rule.id

        # 发送结果消息
        # 创建返回设置按钮
        buttons = [
            [
                Button.inline("👈 返回设置", f"other_settings:{source_id}"),
                Button.inline("❌ 关闭", "close_settings"),
            ]
        ]

        # 删除原消息
        await message.delete()

        # 发送新消息
        await send_message_and_delete(
            event.client,
            event.chat_id,
            result_message,
            buttons=buttons,
            parse_mode="markdown",
        )

        await event.answer(f"已清空规则 {rule.id} 的所有关键字")

    except Exception as e:
        logger.error(f"清空关键字时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"清空关键字失败: {str(e)}")
    return


# 执行清空替换规则的回调
async def callback_perform_clear_replace(event, rule_id_data, session, message, data):
    """执行清空替换规则操作"""
    try:
        # 检查是否包含多个规则ID（格式为source_id:target_id）
        if ":" in rule_id_data:
            # 解析规则ID
            source_rule_id, target_rule_id = await parse_rule_ids(event, rule_id_data)
            if source_rule_id is None or target_rule_id is None:
                return

            # 使用目标规则ID
            rule_id = target_rule_id
        else:
            # 单个规则ID的情况（当前规则）
            rule_id = int(rule_id_data)

        # 获取规则
        rule = session.query(ForwardRule).get(rule_id)
        if not rule:
            await event.answer("规则不存在")
            return

        # 获取并删除所有替换规则
        replace_count = len(rule.replace_rules)

        # 删除所有替换规则
        await session.execute(
            delete(ReplaceRule).filter(ReplaceRule.rule_id == rule.id)
        )
        await session.commit()

        # 构建消息内容
        result_message = f"✅ 已清空规则 `{rule.id}` 的所有替换规则，共删除 {replace_count} 个替换规则"

        # 返回按钮指向源规则的设置页面（如果有的话）
        source_id = int(rule_id_data.split(":")[0]) if ":" in rule_id_data else rule.id

        # 发送结果消息
        # 创建返回设置按钮
        buttons = [
            [
                Button.inline("👈 返回设置", f"other_settings:{source_id}"),
                Button.inline("❌ 关闭", "close_settings"),
            ]
        ]

        # 删除原消息
        await message.delete()

        # 发送新消息
        await send_message_and_delete(
            event.client,
            event.chat_id,
            result_message,
            buttons=buttons,
            parse_mode="markdown",
        )

        await event.answer(f"已清空规则 {rule.id} 的所有替换规则")

    except Exception as e:
        logger.error(f"清空替换规则时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"清空替换规则失败: {str(e)}")
    return


# 执行删除规则的回调
async def callback_perform_delete_rule(event, rule_id_data, session, message, data):
    """执行删除规则操作"""
    try:
        # 检查是否包含多个规则ID（格式为source_id:target_id）
        if ":" in rule_id_data:
            # 尝试使用parse_rule_ids函数解析
            parts = rule_id_data.split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                source_rule_id = int(parts[0])
                target_rule_id = int(parts[1])
                # 使用目标规则ID
                rule_id = target_rule_id
            else:
                # 如果格式不是source_id:target_id，可能是rule_id:page格式
                # 只取第一部分作为规则ID
                rule_id = int(parts[0])
        else:
            # 单个规则ID的情况（当前规则）
            rule_id = int(rule_id_data)

        # 获取规则
        rule = session.query(ForwardRule).get(rule_id)
        if not rule:
            await event.answer("规则不存在")
            return

        # 先保存规则对象，用于后续检查聊天关联
        rule_obj = rule

        # 先删除替换规则
        await session.execute(
            delete(ReplaceRule).filter(ReplaceRule.rule_id == rule.id)
        )

        # 再删除关键字
        await session.execute(delete(Keyword).filter(Keyword.rule_id == rule.id))

        # 删除媒体扩展名
        if hasattr(rule, "media_extensions"):
            await session.execute(
                delete(MediaExtensions).filter(MediaExtensions.rule_id == rule.id)
            )

        # 删除媒体类型
        if hasattr(rule, "media_types"):
            await session.execute(
                delete(MediaTypes).filter(MediaTypes.rule_id == rule.id)
            )

        # 删除规则同步关系
        if hasattr(rule, "rule_syncs"):
            await session.execute(delete(RuleSync).filter(RuleSync.rule_id == rule.id))
            await session.execute(
                delete(RuleSync).filter(RuleSync.sync_rule_id == rule.id)
            )

        # 删除规则
        await session.delete(rule)

        # 提交规则删除的更改
        await session.commit()

        # 尝试删除RSS服务中的相关数据（延迟导入 aiohttp 避免未安装产生波浪线）
        try:
            import importlib

            aiohttp = importlib.import_module("aiohttp")
            rss_url = f"http://{RSS_HOST}:{RSS_PORT}/api/rule/{rule_id}"
            async with aiohttp.ClientSession() as client_session:
                async with client_session.delete(rss_url) as response:
                    if response.status == 200:
                        logger.info(f"成功删除RSS规则数据: {rule_id}")
                    else:
                        response_text = await response.text()
                        logger.warning(
                            f"删除RSS规则数据失败 {rule_id}, 状态码: {response.status}, 响应: {response_text}"
                        )
        except ImportError:
            logger.warning("aiohttp 未安装，跳过调用RSS删除API")
        except Exception as rss_err:
            logger.error(f"调用RSS删除API时出错: {str(rss_err)}")
            # 不影响主要流程，继续执行

        # 使用通用方法检查并清理不再使用的聊天记录
        deleted_chats = await check_and_clean_chats(session, rule_obj)
        if deleted_chats > 0:
            logger.info(f"删除规则后清理了 {deleted_chats} 个未使用的聊天记录")

        # 构建消息内容
        result_message = f"✅ 已删除规则 `{rule.id}`"

        # 删除原消息
        await message.delete()

        # 获取源规则ID（如果有的话）
        source_id = int(rule_id_data.split(":")[0]) if ":" in rule_id_data else None

        # 准备按钮
        if source_id and source_id != rule.id:
            # 如果是从另一个规则删除的，提供返回原规则的按钮
            buttons = [
                [
                    Button.inline("👈 返回设置", f"other_settings:{source_id}"),
                    Button.inline("❌ 关闭", "close_settings"),
                ]
            ]
        else:
            # 如果是删除的当前规则，只提供关闭按钮
            buttons = [[Button.inline("❌ 关闭", "close_settings")]]

        # 发送结果消息
        await send_message_and_delete(
            event.client,
            event.chat_id,
            result_message,
            buttons=buttons,
            parse_mode="markdown",
        )

        await event.answer("规则已成功删除")

    except Exception as e:
        await session.rollback()
        logger.error(f"删除规则时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"删除规则失败: {str(e)}")
    return


async def callback_set_userinfo_template(event, rule_id, session, message, data):
    """设置用户信息模板"""
    logger.info(f"开始处理设置用户信息模板回调 - event: {event}, rule_id: {rule_id}")

    rule = session.query(ForwardRule).get(rule_id)
    if not rule:
        await event.answer("规则不存在")
        return

    # 检查是否频道消息
    if isinstance(event.chat, types.Channel):
        # 检查是否是管理员
        if not await is_admin(event):
            await event.answer("只有管理员可以修改设置")
            return
        user_id = settings.USER_ID

    else:
        user_id = event.sender_id

    chat_id = abs(event.chat_id)
    state = f"set_userinfo_template:{rule_id}"

    logger.info(
        f"准备设置状态 - user_id: {user_id}, chat_id: {chat_id}, state: {state}"
    )
    try:
        # 使用 session_manager 替代 state_manager
        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": state,
            "message": message,
            "state_type": "userinfo",
        }
        # 启动超时取消任务
        asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))
        logger.info("状态设置成功")
    except Exception as e:
        logger.error(f"设置状态时出错: {str(e)}")
        logger.exception(e)

    try:
        current_template = (
            rule.userinfo_template
            if hasattr(rule, "userinfo_template") and rule.userinfo_template
            else "未设置"
        )

        help_text = (
            "用户信息模板用于在转发消息中添加用户信息。\n"
            "可用变量：\n"
            "{name} - 用户名\n"
            "{id} - 用户ID\n"
        )

        await message.edit(
            f"请发送新的用户信息模板\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前用户信息模板：\n\n`{current_template}`\n\n"
            f"{help_text}\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_userinfo:{rule_id}")]],
        )
        logger.info("消息编辑成功")
    except Exception as e:
        logger.error(f"编辑消息时出错: {str(e)}")
        logger.exception(e)
    return


async def callback_set_time_template(event, rule_id, session, message, data):
    """设置时间模板"""
    logger.info(f"开始处理设置时间模板回调 - event: {event}, rule_id: {rule_id}")

    rule = session.query(ForwardRule).get(rule_id)
    if not rule:
        await event.answer("规则不存在")
        return

    # 检查是否频道消息
    if isinstance(event.chat, types.Channel):
        # 检查是否是管理员
        if not await is_admin(event):
            await event.answer("只有管理员可以修改设置")
            return
        user_id = settings.USER_ID

    else:
        user_id = event.sender_id

    chat_id = abs(event.chat_id)
    state = f"set_time_template:{rule_id}"

    logger.info(
        f"准备设置状态 - user_id: {user_id}, chat_id: {chat_id}, state: {state}"
    )
    try:
        # 使用 session_manager 替代 state_manager
        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": state,
            "message": message,
            "state_type": "time",
        }
        # 启动超时取消任务
        asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))
        logger.info("状态设置成功")
    except Exception as e:
        logger.error(f"设置状态时出错: {str(e)}")
        logger.exception(e)

    try:
        current_template = (
            rule.time_template
            if hasattr(rule, "time_template") and rule.time_template
            else "未设置"
        )

        help_text = (
            "时间模板用于在转发消息中添加时间信息。\n"
            "可用变量:\n"
            "{time} - 当前时间\n"
        )

        await message.edit(
            f"请发送新的时间模板\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前时间模板：\n\n`{current_template}`\n\n"
            f"{help_text}\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_time:{rule_id}")]],
        )
        logger.info("消息编辑成功")
    except Exception as e:
        logger.error(f"编辑消息时出错: {str(e)}")
        logger.exception(e)
    return


async def cancel_state_after_timeout(
    user_id: int, chat_id: int, timeout_minutes: int = 5
):
    """在指定时间后自动取消状态"""
    await asyncio.sleep(timeout_minutes * 60)
    # 使用 session_manager 替代 state_manager
    user_session = session_manager.user_sessions.get(user_id, {})
    chat_state = user_session.get(chat_id, {})
    current_state = chat_state.get("state")
    if current_state:  # 只有当状态还存在时才清除
        logger.info(f"状态超时自动取消 - user_id: {user_id}, chat_id: {chat_id}")
        user_session.pop(chat_id)
        # 如果用户会话为空，清理掉该用户的会话记录
        if not user_session:
            session_manager.user_sessions.pop(user_id)


async def callback_cancel_set_userinfo(event, rule_id, session, message, data):
    """取消设置用户信息模板"""
    rule_id = data.split(":")[1]
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            # 清除状态
            # 使用 session_manager 替代 state_manager
            user_id = event.sender_id
            chat_id = abs(event.chat_id)
            if user_id in session_manager.user_sessions:
                if chat_id in session_manager.user_sessions[user_id]:
                    session_manager.user_sessions[user_id].pop(chat_id)
                    # 如果用户会话为空，清理掉该用户的会话记录
                    if not session_manager.user_sessions[user_id]:
                        session_manager.user_sessions.pop(user_id)
            # 返回到其他设置页面
            await event.edit(
                "其他设置：",
                buttons=await create_other_settings_buttons(rule_id=rule_id),
            )
            await event.answer("已取消设置")
    finally:
        session.close()
    return


async def callback_cancel_set_time(event, rule_id, session, message, data):
    """取消设置时间模板"""
    rule_id = data.split(":")[1]
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            # 清除状态
            # 使用 session_manager 替代 state_manager
            user_id = event.sender_id
            chat_id = abs(event.chat_id)
            if user_id in session_manager.user_sessions:
                if chat_id in session_manager.user_sessions[user_id]:
                    session_manager.user_sessions[user_id].pop(chat_id)
                    # 如果用户会话为空，清理掉该用户的会话记录
                    if not session_manager.user_sessions[user_id]:
                        session_manager.user_sessions.pop(user_id)
            # 返回到其他设置页面
            await event.edit(
                "其他设置：",
                buttons=await create_other_settings_buttons(rule_id=rule_id),
            )
            await event.answer("已取消设置")
    finally:
        session.close()
    return


async def callback_set_original_link_template(event, rule_id, session, message, data):
    """设置原始链接模板"""
    logger.info(f"开始处理设置原始链接模板回调 - event: {event}, rule_id: {rule_id}")

    rule = session.query(ForwardRule).get(rule_id)
    if not rule:
        await event.answer("规则不存在")
        return

    # 检查是否频道消息
    if isinstance(event.chat, types.Channel):
        # 检查是否是管理员
        if not await is_admin(event):
            await event.answer("只有管理员可以修改设置")
            return
        user_id = settings.USER_ID

    else:
        user_id = event.sender_id

    chat_id = abs(event.chat_id)
    state = f"set_original_link_template:{rule_id}"

    logger.info(
        f"准备设置状态 - user_id: {user_id}, chat_id: {chat_id}, state: {state}"
    )
    try:
        # 使用 session_manager 替代 state_manager
        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": state,
            "message": message,
            "state_type": "link",
        }
        # 启动超时取消任务
        asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))
        logger.info("状态设置成功")
    except Exception as e:
        logger.error(f"设置状态时出错: {str(e)}")
        logger.exception(e)

    try:
        current_template = (
            rule.original_link_template
            if hasattr(rule, "original_link_template") and rule.original_link_template
            else "未设置"
        )

        help_text = (
            "原始链接模板用于在转发消息中添加原始链接。\n"
            "可用变量:\n"
            "{original_link} - 完整的原始链接\n"
        )

        await message.edit(
            f"请发送新的原始链接模板\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前原始链接模板：\n\n`{current_template}`\n\n"
            f"{help_text}\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_link:{rule_id}")]],
        )
        logger.info("消息编辑成功")
    except Exception as e:
        logger.error(f"编辑消息时出错: {str(e)}")
        logger.exception(e)
    return


async def callback_cancel_set_original_link(event, rule_id, session, message, data):
    """取消设置原始链接模板"""
    rule_id = data.split(":")[1]
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            # 清除状态
            # 使用 session_manager 替代 state_manager
            user_id = event.sender_id
            chat_id = abs(event.chat_id)
            if user_id in session_manager.user_sessions:
                if chat_id in session_manager.user_sessions[user_id]:
                    session_manager.user_sessions[user_id].pop(chat_id)
                    # 如果用户会话为空，清理掉该用户的会话记录
                    if not session_manager.user_sessions[user_id]:
                        session_manager.user_sessions.pop(user_id)
            # 返回到其他设置页面
            await event.edit(
                "其他设置：",
                buttons=await create_other_settings_buttons(rule_id=rule_id),
            )
            await event.answer("已取消设置")
    finally:
        session.close()
    return


async def callback_toggle_reverse_blacklist(event, rule_id, session, message, data):
    """切换反转黑名单设置"""
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            rule.enable_reverse_blacklist = not rule.enable_reverse_blacklist
            session.commit()
            await event.answer("设置已更新")

            await event.edit(
                buttons=await create_other_settings_buttons(rule_id=rule_id)
            )
    except Exception as e:
        logger.error(f"切换反转黑名单设置时出错: {str(e)}")
        await event.answer("更新设置失败")
    return


async def callback_toggle_reverse_whitelist(event, rule_id, session, message, data):
    """切换反转白名单设置"""
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            rule.enable_reverse_whitelist = not rule.enable_reverse_whitelist
            session.commit()
            await event.answer("设置已更新")

            await event.edit(
                buttons=await create_other_settings_buttons(rule_id=rule_id)
            )
    except Exception as e:
        logger.error(f"切换反转白名单设置时出错: {str(e)}")
        await event.answer("更新设置失败")
    return
