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
    async with container.db.get_session(session) as s:
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

async def callback_rule_settings(event, rule_id, session, message, data):
    """处理规则设置的回调"""
    async with container.db.get_session(session) as s:
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
            async with container.db.get_session(session) as s:
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
        except Exception as e:
            logger.error(f"设置延迟时间时出错: {str(e)}")
    return

async def update_rule_setting(
    event, rule_id, message, field_name, config, setting_type, session=None
):
    """通用的规则设置更新函数"""
    logger.info(f"找到匹配的设置项: {field_name}")

    async with container.db.get_session(session) as s:
        # 1. 加载主规则 (仅预加载必要的同步信息)
        stmt = (
            select(ForwardRule)
            .options(selectinload(ForwardRule.rule_syncs))
            .where(ForwardRule.id == int(rule_id))
        )
        result = await s.execute(stmt)
        rule = result.scalar_one_or_none()
        
        if not rule:
            logger.warning(f"规则不存在: {rule_id}")
            await event.answer("规则不存在")
            return False

        current_value = getattr(rule, field_name)
        new_value = config["toggle_func"](current_value)
        setattr(rule, field_name, new_value)

        try:
            # 2. 处理同步逻辑
            if rule.enable_sync and field_name not in ("enable_rule", "enable_sync"):
                # 获取同步列表 ID
                target_ids = [sr.sync_rule_id for sr in rule.rule_syncs]
                if target_ids:
                    logger.info(f"正在同步设置 {field_name} 到 {len(target_ids)} 个规则")
                    # 批量更新 (直接执行 SQL UPDATE 效率最高，不需要全量加载模型)
                    from sqlalchemy import update
                    sync_stmt = (
                        update(ForwardRule)
                        .where(ForwardRule.id.in_(target_ids))
                        .values({field_name: new_value})
                    )
                    await s.execute(sync_stmt)

            await s.commit()
            logger.info(f"已更新规则 {rule_id} 及其同步规则: {field_name}={new_value}")

        except Exception as e:
            logger.error(f"更新规则设置失败: {e}")
            await event.answer("更新失败")
            return False

        # 3. 刷新 UI (仅加载刷新界面所需的最小关联)
        # 性能优化：按需加载关联，而不是 selectinload(*)
        if setting_type == "rule":
             # 规则设置界面需要加载 source/target_chat
             await s.refresh(rule, ["source_chat", "target_chat"])
             await message.edit(await create_settings_text(rule), buttons=await create_buttons(rule))
        elif setting_type == "media":
             await s.refresh(rule, ["media_types", "media_extensions"])
             await event.edit("媒体设置：", buttons=await create_media_settings_buttons(rule))
        elif setting_type == "ai":
             await message.edit(await get_ai_settings_text(rule), buttons=await create_ai_settings_buttons(rule))
        elif setting_type == "other":
             # 其他设置通常不需要预加载复杂关联
             await event.edit("其他设置：", buttons=await create_other_settings_buttons(rule))
        elif setting_type == "push":
             await s.refresh(rule, ["push_config"])
             await event.edit(PUSH_SETTINGS_TEXT, buttons=await create_push_settings_buttons(rule, session=s), link_preview=False)

        await event.answer(f"已更新 {config.get('display_name', field_name)}")
        return True
