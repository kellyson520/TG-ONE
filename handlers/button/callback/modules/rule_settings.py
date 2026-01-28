import logging
from telethon import Button
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models.models import Chat, ForwardRule
from core.container import container
from core.helpers.id_utils import find_chat_by_telegram_id_variants
from handlers.button.settings_manager import create_buttons, create_settings_text, get_ai_settings_text, create_ai_settings_buttons
from handlers.button.button_helpers import create_delay_time_buttons, create_other_settings_buttons, create_media_settings_buttons, create_push_settings_buttons
from core.constants import PUSH_SETTINGS_TEXT

logger = logging.getLogger(__name__)

async def callback_settings(event, rule_id, session, message, data):
    """处理显示设置的回调"""
    async def _do(s):
        current_chat = await event.get_chat()
        
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

async def callback_rule_settings(event, rule_id, session, message, data):
    """处理规则设置的回调"""
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

async def update_rule_setting(
    event, rule_id, message, field_name, config, setting_type
):
    """通用的规则设置更新函数"""
    logger.info(f"找到匹配的设置项: {field_name}")

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
                from models.models import RuleSync
                sync_rules = await session.execute(
                     select(RuleSync).where(RuleSync.rule_id == rule.id)
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
