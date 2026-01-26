import traceback

import logging
from telethon import Button
from services.network.router import RadixRouter

from models.models import (
    AsyncSessionManager,
    Chat,
    ForwardRule,
    Keyword,
    ReplaceRule,
    RuleSync,
    SessionManager,
)

# aiohttp 在某些环境未安装会导致编辑器波浪线，这里保持局部延迟导入
# [Refactor Fix] 更新 constants 路径
from utils.core.constants import RSS_HOST, RSS_PORT

# [Refactor Fix] 更新 common 路径
from core.helpers.common import check_and_clean_chats

# [Refactor Fix] 更新 id_utils 路径
from core.helpers.id_utils import find_chat_by_telegram_id_variants

# [Refactor Fix] 更新 auto_delete 路径
from utils.processing.auto_delete import reply_and_delete, respond_and_delete

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from handlers.list_handlers import show_list
from handlers.button.button_helpers import (
    create_delay_time_buttons,
    create_other_settings_buttons,
    create_sync_rule_buttons,
)
from handlers.button.settings_manager import (
    AI_SETTINGS,
    MEDIA_SETTINGS,
    RULE_SETTINGS,
    create_buttons,
    create_settings_text,
)

# 导入管理面板回调
from .admin_callback import (
    callback_admin_cleanup,
    callback_admin_cleanup_menu,
    callback_admin_cleanup_temp,
    callback_admin_config,
    callback_admin_db_backup,
    callback_admin_db_health,
    callback_admin_db_info,
    callback_admin_db_optimize,
    callback_admin_logs,
    callback_admin_panel,
    callback_admin_restart,
    callback_admin_restart_confirm,
    callback_admin_stats,
    callback_admin_system_status,
    callback_close_admin_panel,
)

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
from .ai_callback import callback_set_summary_time  # 移动到这里
from .ai_callback import (
    callback_ai_settings,
    callback_cancel_set_prompt,
    callback_cancel_set_summary,
    callback_change_model,
    callback_model_page,
    callback_select_model,
    callback_select_time,
    callback_set_ai_prompt,
    callback_set_summary_prompt,
    callback_summary_now,
    callback_time_page,
    handle_ai_callback,
)

# 导入媒体设置回调
from .media_callback import (
    callback_media_extensions_page,
    callback_media_settings,
    callback_select_max_media_size,
    callback_set_max_media_size,
    callback_set_media_extensions,
    callback_set_media_types,
    callback_toggle_media_allow_text,
    callback_toggle_media_extension,
    callback_toggle_media_type,
    handle_media_callback,
)
from .new_menu_callback import handle_new_menu_callback

# 导入其他通用设置回调
from .other_callback import (
    callback_cancel_set_original_link,
    callback_cancel_set_time,
    callback_cancel_set_userinfo,
    callback_clear_keyword,
    callback_clear_replace,
    callback_confirm_delete_duplicates,
    callback_copy_keyword,
    callback_copy_replace,
    callback_copy_rule,
    callback_dedup_scan_now,
    callback_delete_duplicates,
    callback_delete_rule,
    callback_keep_duplicates,
    callback_other_settings,
    callback_perform_clear_keyword,
    callback_perform_clear_replace,
    callback_perform_copy_keyword,
    callback_perform_copy_replace,
    callback_perform_copy_rule,
    callback_perform_delete_rule,
    callback_set_original_link_template,
    callback_set_time_template,
    callback_set_userinfo_template,
    callback_toggle_allow_delete_source_on_dedup,
    callback_toggle_reverse_blacklist,
    callback_toggle_reverse_whitelist,
    callback_view_source_messages,
    handle_other_callback,
)

# 导入推送设置回调
from .push_callback import (
    callback_add_push_channel,
    callback_cancel_add_push_channel,
    callback_delete_push_config,
    callback_push_page,
    callback_push_settings,
    callback_toggle_enable_only_push,
    callback_toggle_enable_push,
    callback_toggle_media_send_mode,
    callback_toggle_push_config,
    callback_toggle_push_config_status,
)
from .search_callback import handle_search_callback

logger = logging.getLogger(__name__)


async def callback_switch(event, rule_id, session, message, data):
    """处理切换源聊天的回调"""
    from core.container import container
    from core.helpers.id_utils import find_chat_by_telegram_id_variants

    # 内部执行逻辑
    async def _do(s):
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

    if session is None:
        async with container.db_session() as s:
            await _do(s)
    else:
        await _do(session)


async def callback_settings(event, rule_id, session, message, data):
    """处理显示设置的回调"""
    from core.container import container
    from core.helpers.id_utils import find_chat_by_telegram_id_variants

    async def _do(s):
        current_chat = await event.get_chat()
        
        # 使用 selectinload 预加载关联以避免 lazy load 错误
        stmt = select(Chat).where(Chat.telegram_chat_id == str(current_chat.id))
        result = await s.execute(stmt)
        current_chat_db = result.scalar_one_or_none()
        
        if not current_chat_db:
            current_chat_db = find_chat_by_telegram_id_variants(s, current_chat.id)

        if not current_chat_db:
            await event.answer("当前聊天不存在")
            return

        rules = await s.execute(
            container.rule_repo.get_rules_for_target_chat(current_chat_db.id)
        )
        rules_list = rules.scalars().all()

        if not rules_list:
            await event.answer("当前聊天没有任何转发规则")
            return

        buttons = []
        for rule in rules_list:
            source_chat = rule.source_chat
            button_text = f"{source_chat.name}"
            callback_data = f"rule_settings:{rule.id}"
            buttons.append([Button.inline(button_text, callback_data)])

        await message.edit("请选择要管理的转发规则:", buttons=buttons)

    if session is None:
        async with container.db_session() as s:
            await _do(s)
    else:
        await _do(session)


async def callback_delete(event, rule_id, session, message, data):
    """处理删除规则的回调"""
    from core.container import container
    from core.helpers.common import check_and_clean_chats

    async def _do(s):
        from models.models import ForwardRule
        rule = await s.get(ForwardRule, int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        try:
            rule_obj = rule
            # 删除关联数据
            from sqlalchemy import text
            await s.execute(text("DELETE FROM replace_rule WHERE rule_id = :rule_id"), {"rule_id": rule.id})
            await s.execute(text("DELETE FROM keyword WHERE rule_id = :rule_id"), {"rule_id": rule.id})
            await s.delete(rule)
            await s.commit()

            # 清理 RSS 数据 (直接调用函数而非HTTP请求)
            try:
                from rss.app.api.endpoints.feed import delete_rule_data
                await delete_rule_data(int(rule_id))
                logger.info(f"成功删除RSS规则数据: {rule_id}")
            except Exception as e:
                logger.warning(f"删除RSS数据遇到错误 (由于规则已删除，可忽略): {e}")

        except Exception as e:
            await s.rollback()
            logger.error(f"删除规则时出错: {str(e)}")
            await event.answer("删除规则失败")
            return

        await check_and_clean_chats(rule_obj)
        await message.delete()
        await respond_and_delete(event, ("✅ 已删除规则"))
        await event.answer("已删除规则")

    if session is None:
        async with container.db_session() as s:
            await _do(s)
    else:
        await _do(session)
async def callback_page(event, rule_id, session, message, data):
    """处理翻页的回调"""
    logger.info(f"翻页回调数据: action=page, rule_id={rule_id}")
    from core.container import container

    async def _do(s):
        try:
            page_number, command = rule_id.split(":")
            page = int(page_number)
            from core.helpers.id_utils import find_chat_by_telegram_id_variants

            current_chat = await event.get_chat()
            current_chat_db = await s.execute(
                "SELECT * FROM chat WHERE telegram_chat_id = :chat_id",
                {"chat_id": str(current_chat.id)},
            )
            current_chat_db = current_chat_db.scalar()

            if not current_chat_db or not current_chat_db.current_add_id:
                await event.answer("请先选择一个源聊天")
                return

            source_chat = find_chat_by_telegram_id_variants(s, current_chat_db.current_add_id)
            rule = await s.execute(
                "SELECT * FROM forward_rule WHERE source_chat_id = :source_id AND target_chat_id = :target_id",
                {"source_id": source_chat.id, "target_id": current_chat_db.id},
            )
            rule = rule.scalar()

            if command == "keyword":
                keywords = await s.execute(
                    "SELECT * FROM keyword WHERE rule_id = :rule_id",
                    {"rule_id": rule.id},
                )
                keywords = keywords.scalars().all()
                await show_list(event, "keyword", keywords, lambda i, kw: f'{i}. {kw.keyword}{" (正则)" if kw.is_regex else ""}', f"关键字列表\n规则: 来自 {source_chat.name}", page)
            elif command == "replace":
                replace_rules = await s.execute(
                    "SELECT * FROM replace_rule WHERE rule_id = :rule_id",
                    {"rule_id": rule.id},
                )
                replace_rules = replace_rules.scalars().all()
                await show_list(event, "replace", replace_rules, lambda i, rr: f'{i}. 匹配: {rr.pattern} -> {"删除" if not rr.content else f"替换为: {rr.content}"}', f"替换规则列表\n规则: 来自 {source_chat.name}", page)
            await event.answer()
        except Exception as e:
            logger.error(f"处理翻页时出错: {str(e)}")
            await event.answer("处理翻页时出错，请检查日志")

    if session is None:
        async with container.db_session() as s:
            await _do(s)
    else:
        await _do(session)


async def callback_rule_settings(event, rule_id, session, message, data):
    """处理规则设置的回调"""
    from core.container import container
    async def _do(s):
        # 使用 selectinload 预加载 source_chat 和 target_chat，防止 MissingGreenlet
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
        await message.edit(await create_settings_text(rule), buttons=await create_buttons(rule))

    if session is None:
        async with container.db_session() as s:
            await _do(s)
    else:
        await _do(session)


async def callback_toggle_current(event, rule_id, session, message, data):
    """处理切换当前规则的回调"""
    from core.container import container
    async def _do(s):
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
            await message.edit(await create_settings_text(rule), buttons=await create_buttons(rule))
        except Exception as e:
            if "message was not modified" not in str(e).lower():
                raise
        await event.answer(f"已切换到: {source_chat.name}")

    if session is None:
        async with container.db_session() as s:
            await _do(s)
    else:
        await _do(session)


async def callback_set_delay_time(event, rule_id, session, message, data):
    await event.edit(
        "请选择延迟时间：", buttons=await create_delay_time_buttons(rule_id, page=0)
    )
    return


async def callback_delay_time_page(event, rule_id, session, message, data):
    _, rule_id, page = data.split(":")
    page = int(page)
    await event.edit(
        "请选择延迟时间：", buttons=await create_delay_time_buttons(rule_id, page=page)
    )
    return


async def callback_select_delay_time(event, rule_id, session, message, data):
    parts = data.split(":", 2)  # 最多分割2次
    if len(parts) == 3:
        _, rule_id, time = parts
        logger.info(f"设置规则 {rule_id} 的延迟时间为: {time}")
        try:
            from core.container import container
            async def _do(s):
                # 使用 selectinload 预加载关联
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
                if rule:
                    rule.delay_seconds = int(time)
                    await s.commit()
                    msg_obj = await event.get_message()
                    await msg_obj.edit(await create_settings_text(rule), buttons=await create_buttons(rule))
            if session is None:
                async with container.db_session() as s: await _do(s)
            else:
                await _do(session)
        except Exception as e:
            logger.error(f"设置延迟时间时出错: {str(e)}")
    return


async def callback_set_sync_rule(event, rule_id, session, message, data):
    """处理设置同步规则的回调"""
    try:
        from core.container import container
        async def _do(s):
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule:
                await event.answer("规则不存在")
                return
            await message.edit("请选择要同步到的规则：", buttons=await create_sync_rule_buttons(rule_id, page=0))
        
        if session is None:
            async with container.db_session() as s: await _do(s)
        else:
            await _do(session)
    except Exception as e:
        logger.error(f"设置同步规则时出错: {str(e)}")
    return


async def callback_toggle_rule_sync(event, rule_id_data, session, message, data):
    """处理切换规则同步状态的回调"""
    try:
        parts = rule_id_data.split(":")
        source_rule_id = int(parts[0])
        target_rule_id = int(parts[1])
        page = int(parts[2])

        from core.container import container
        async def _do(s):
            syncs = await s.execute("SELECT * FROM rule_sync WHERE rule_id = :rule_id", {"rule_id": source_rule_id})
            syncs = syncs.scalars().all()
            sync_target_ids = [sync.sync_rule_id for sync in syncs]

            if target_rule_id in sync_target_ids:
                await s.execute("DELETE FROM rule_sync WHERE rule_id = :source_id AND sync_rule_id = :target_id", {"source_id": source_rule_id, "target_id": target_rule_id})
                await s.commit()
                await event.answer(f"已取消同步规则 {target_rule_id}")
            else:
                from models.models import RuleSync
                new_sync = RuleSync(rule_id=source_rule_id, sync_rule_id=target_rule_id)
                s.add(new_sync)
                await s.commit()
                await event.answer(f"已设置同步到规则 {target_rule_id}")
            await message.edit("请选择要同步到的规则：", buttons=await create_sync_rule_buttons(source_rule_id, page))

        if session is None:
            async with container.db_session() as s: await _do(s)
        else:
            await _do(session)
    except Exception as e:
        logger.error(f"切换规则同步状态时出错: {str(e)}")
    return


async def callback_sync_rule_page(event, rule_id_data, session, message, data):
    """处理同步规则页面的翻页功能"""
    try:
        parts = rule_id_data.split(":")
        rule_id = int(parts[0])
        page = int(parts[1])
        from core.container import container
        async def _do(s):
            rule = await s.get(ForwardRule, rule_id)
            if not rule:
                await event.answer("规则不存在")
                return
            await message.edit("请选择要同步到的规则：", buttons=await create_sync_rule_buttons(rule_id, page))

        if session is None:
            async with container.db_session() as s: await _do(s)
        else:
            await _do(session)
    except Exception as e:
        logger.error(f"处理同步规则页面翻页时出错: {str(e)}")
    return


async def callback_close_settings(event, rule_id, session, message, data):
    """处理关闭设置按钮的回调，删除当前消息"""
    try:
        await message.delete()
    except Exception as e:
        logger.error(f"删除消息时出错: {str(e)}")
    return


async def callback_noop(event, rule_id, session, message, data):
    await event.answer("当前页码")
    return


async def callback_page_rule(event, page_str, session, message, data):
    """处理规则列表分页的回调"""
    try:
        page = int(page_str)
        from core.container import container

        async def _do(s):
            total_result = await s.execute("SELECT COUNT(*) FROM forward_rule")
            total_rules = total_result.scalar()
            if total_rules == 0:
                await event.answer("没有任何规则")
                return
            per_page = 30
            total_pages = (total_rules + per_page - 1) // per_page
            offset = (page - 1) * per_page
            rules = await s.execute("SELECT * FROM forward_rule ORDER BY id OFFSET :offset LIMIT :limit", {"offset": offset, "limit": per_page})
            rules = rules.scalars().all()
            
            message_parts = [f"📋 转发规则列表 (第{page}/{total_pages}页)：\n"]
            for rule in rules:
                rule_desc = f"<b>ID: {rule.id}</b>\n<blockquote>来源: {rule.source_chat.name}\n目标: {rule.target_chat.name}</blockquote>"
                message_parts.append(rule_desc)
            
            buttons = []
            nav_row = []
            nav_row.append(Button.inline("⬅️ 上一页" if page > 1 else "⬅️", f"page_rule:{page-1}" if page > 1 else "noop"))
            nav_row.append(Button.inline(f"{page}/{total_pages}", "noop"))
            nav_row.append(Button.inline("下一页 ➡️" if page < total_pages else "➡️", f"page_rule:{page+1}" if page < total_pages else "noop"))
            buttons.append(nav_row)
            await message.edit("\n".join(message_parts), buttons=buttons, parse_mode="html")
        
        if session is None:
            async with container.db_session() as s: await _do(s)
        else:
            await _do(session)
    except Exception as e:
        logger.error(f"处理规则列表分页出错: {e}")
    return


async def update_rule_setting(
    event, rule_id, message, field_name, config, setting_type
):
    """通用的规则设置更新函数

    Args:
        event: 回调事件
        rule_id: 规则ID
        message: 消息对象
        field_name: 字段名
        config: 设置配置
        setting_type: 设置类型 ('rule', 'media', 'ai')
    """
    logger.info(f"找到匹配的设置项: {field_name}")

    from core.container import container

    async with container.db_session() as session:
        # 使用 selectinload 预加载关联
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
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        if not rule:
            logger.warning(f"规则不存在: {rule_id}")
            await event.answer("规则不存在")
            return False

        current_value = getattr(rule, field_name)
        new_value = config["toggle_func"](current_value)
        setattr(rule, field_name, new_value)

        try:
            # 首先更新当前规则
            await session.commit()
            logger.info(
                f"更新规则 {rule.id} 的 {field_name} 从 {current_value} 到 {new_value}"
            )

            # 检查是否启用了同步功能，且不是"是否启用规则"字段和"启用同步"字段
            if (
                rule.enable_sync
                and field_name != "enable_rule"
                and field_name != "enable_sync"
            ):
                logger.info(
                    f"规则 {rule.id} 启用了同步功能，正在同步设置更改到关联规则"
                )
                # 获取需要同步的规则列表
                sync_rules = await session.execute(
                    "SELECT * FROM rule_sync WHERE rule_id = :rule_id",
                    {"rule_id": rule.id},
                )
                sync_rules = sync_rules.scalars().all()

                # 为每个同步规则应用相同的设置
                for sync_rule in sync_rules:
                    sync_rule_id = sync_rule.sync_rule_id
                    logger.info(f"正在同步设置 {field_name} 到规则 {sync_rule_id}")

                    # 获取同步目标规则
                    target_rule = await session.get(ForwardRule, sync_rule_id)
                    if not target_rule:
                        logger.warning(f"同步目标规则 {sync_rule_id} 不存在，跳过")
                        continue

                    # 更新同步目标规则的设置
                    try:
                        # 记录旧值
                        old_value = getattr(target_rule, field_name)

                        # 设置新值
                        setattr(target_rule, field_name, new_value)
                        await session.flush()

                        logger.info(
                            f"同步规则 {sync_rule_id} 的 {field_name} 从 {old_value} 到 {new_value}"
                        )
                    except Exception as e:
                        logger.error(f"同步设置到规则 {sync_rule_id} 时出错: {str(e)}")
                        continue

                # 提交所有同步更改
                await session.commit()
                logger.info("所有同步更改已提交")

        except Exception as e:
            await session.rollback()
            logger.error(f"更新规则设置时出错: {str(e)}")
            await event.answer("更新设置失败，请检查日志")
            return False

    # 根据设置类型更新UI
    async with container.db_session() as session:
        # 使用 selectinload 预加载关联
        stmt = (
            select(ForwardRule)
            .options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat)
            )
            .where(ForwardRule.id == int(rule_id))
        )
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        if setting_type == "rule":
            await message.edit(
                await create_settings_text(rule), buttons=await create_buttons(rule)
            )
        elif setting_type == "media":
            await event.edit(
                "媒体设置：", buttons=await create_media_settings_buttons(rule)
            )
        elif setting_type == "ai":
            await message.edit(
                await get_ai_settings_text(rule),
                buttons=await create_ai_settings_buttons(rule),
            )
        elif setting_type == "other":
            await event.edit(
                "其他设置：", buttons=await create_other_settings_buttons(rule)
            )
        elif setting_type == "push":
            await event.edit(
                PUSH_SETTINGS_TEXT,
                buttons=await create_push_settings_buttons(rule),
                link_preview=False,
            )
        display_name = config.get("display_name", field_name)
        if field_name == "use_bot":
            await event.answer(f'已切换到{"机器人" if new_value else "用户账号"}模式')
        else:
            await event.answer(f"已更新{display_name}")
        return True


async def handle_callback(event):
    """处理所有回调查询 (已完成 RadixRouter 重构)"""
    try:
        data = event.data.decode("utf-8")
        logger.debug(f"Router分派: {data}")

        # [Phase 3] 彻底重构成基于路由的分分派，移除“双轨制” waterfall
        handler, params = callback_router.match(data)
        if handler:
            # 将 params 注入 event 以供 handler 使用（如果需要）
            event.router_params = params
            return await handler(event)

        # 降级处理 (异常或未定义的路由)
        logger.warning(f"未找到路由处理程序: {data}")
        await event.answer("未处理的操作", alert=False)

    except Exception as e:
        logger.error(f"回调处理异常: {e}\n{traceback.format_exc()}")
        try:
            await event.answer("操作处理出错，请重试", alert=True)
        except:
            pass


# 回调处理器字典
CALLBACK_HANDLERS = {
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
    # AI设置
    "set_summary_prompt": callback_set_summary_prompt,
    "set_ai_prompt": callback_set_ai_prompt,
    "ai_settings": callback_ai_settings,
    "time_page": callback_time_page,
    "select_time": callback_select_time,
    "select_model": callback_select_model,
    "model_page": callback_model_page,
    "change_model": callback_change_model,
    "cancel_set_prompt": callback_cancel_set_prompt,
    "cancel_set_summary": callback_cancel_set_summary,
    "summary_now": callback_summary_now,
    # 媒体设置
    "select_max_media_size": callback_select_max_media_size,
    "set_max_media_size": callback_set_max_media_size,
    "media_settings": callback_media_settings,
    "set_media_types": callback_set_media_types,
    "toggle_media_type": callback_toggle_media_type,
    "set_media_extensions": callback_set_media_extensions,
    "media_extensions_page": callback_media_extensions_page,
    "toggle_media_extension": callback_toggle_media_extension,
    "toggle_media_allow_text": callback_toggle_media_allow_text,
    "noop": callback_noop,
    # 其他设置
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
    # 推送设置
    "push_settings": callback_push_settings,
    "toggle_enable_push": callback_toggle_enable_push,
    "toggle_enable_only_push": callback_toggle_enable_only_push,
    "add_push_channel": callback_add_push_channel,
    "cancel_add_push_channel": callback_cancel_add_push_channel,
    "toggle_push_config": callback_toggle_push_config,
    "toggle_push_config_status": callback_toggle_push_config_status,
    "toggle_media_send_mode": callback_toggle_media_send_mode,
    "delete_push_config": callback_delete_push_config,
    "push_page": callback_push_page,
    # 管理面板回调
    "admin_db_info": callback_admin_db_info,
    "admin_db_health": callback_admin_db_health,
    "admin_db_backup": callback_admin_db_backup,
    "admin_db_optimize": callback_admin_db_optimize,
    "admin_system_status": callback_admin_system_status,
    "admin_logs": callback_admin_logs,
    "admin_cleanup_menu": callback_admin_cleanup_menu,
    "admin_cleanup": callback_admin_cleanup,
    "admin_cleanup_temp": callback_admin_cleanup_temp,
    "admin_vacuum_db": callback_admin_db_optimize,  # 重用优化功能
    "admin_analyze_db": callback_admin_db_optimize,  # 重用优化功能
    "admin_full_optimize": callback_admin_db_optimize,  # 重用优化功能
    "admin_stats": callback_admin_stats,
    "admin_config": callback_admin_config,
    "admin_restart": callback_admin_restart,
    "admin_restart_confirm": callback_admin_restart_confirm,
    "admin_panel": callback_admin_panel,
    "close_admin_panel": callback_close_admin_panel,
    # 高级媒体筛选回调
    "toggle_duration_filter": callback_toggle_duration_filter,
    "set_duration_range": callback_set_duration_range,
    "cancel_set_duration_range": callback_cancel_set_duration_range,
    "toggle_resolution_filter": callback_toggle_resolution_filter,
    "set_resolution_range": callback_set_resolution_range,
    "cancel_set_resolution_range": callback_cancel_set_resolution_range,
    "toggle_file_size_range_filter": callback_toggle_file_size_range_filter,
    "set_file_size_range": callback_set_file_size_range,
    "cancel_set_file_size_range": callback_cancel_set_file_size_range,
    # 去重按钮回调
    "delete_duplicates": callback_delete_duplicates,
    "view_source_messages": callback_view_source_messages,
    "keep_duplicates": callback_keep_duplicates,
    "confirm_delete_duplicates": callback_confirm_delete_duplicates,
    "toggle_allow_delete_source_on_dedup": callback_toggle_allow_delete_source_on_dedup,
}

# 初始化全局路由器
callback_router = RadixRouter()
callback_router.build_from_dict(CALLBACK_HANDLERS)

# 添加带参数的高级路由支持
callback_router.add_route("rule:{id}:settings", callback_rule_settings)
callback_router.add_route("delete:{id}", callback_delete)
callback_router.add_route("switch:{id}", callback_switch)

# [Phase 3 Extension] 整合原本在 if/else 中处理的通配路由
callback_router.add_route("new_menu:{rest}", handle_new_menu_callback)
callback_router.add_route("search_{rest}", handle_search_callback)
callback_router.add_route("media_settings{rest}", handle_media_callback)
callback_router.add_route("set_max_media_size{rest}", handle_media_callback)
callback_router.add_route("select_max_media_size{rest}", handle_media_callback)
callback_router.add_route("set_media_types{rest}", handle_media_callback)
callback_router.add_route("toggle_media_type{rest}", handle_media_callback)
callback_router.add_route("set_media_extensions{rest}", handle_media_callback)
callback_router.add_route("media_extensions_page{rest}", handle_media_callback)
callback_router.add_route("toggle_media_extension{rest}", handle_media_callback)
callback_router.add_route("toggle_media_allow_text{rest}", handle_media_callback)

# 高级媒体筛选路由
callback_router.add_route("open_duration_picker{rest}", handle_advanced_media_callback)

# 其他设置路由
callback_router.add_route("ai_settings{rest}", handle_ai_callback)
callback_router.add_route("set_summary_time{rest}", handle_ai_callback)
callback_router.add_route("other_callback{rest}", handle_other_callback)
