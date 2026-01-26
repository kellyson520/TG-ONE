import logging
from handlers.button.button_helpers import create_sync_rule_buttons
from models.models import ForwardRule, RuleSync
from core.container import container
from sqlalchemy import select

logger = logging.getLogger(__name__)

async def callback_set_sync_rule(event, rule_id, session, message, data):
    """处理设置同步规则的回调"""
    try:
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

        async def _do(s):
            syncs = await s.execute(select(RuleSync).where(RuleSync.rule_id == source_rule_id))
            syncs = syncs.scalars().all()
            sync_target_ids = [sync.sync_rule_id for sync in syncs]

            if target_rule_id in sync_target_ids:
                # Use text for delete or ORM delete
                from sqlalchemy import delete
                stmt = delete(RuleSync).where(RuleSync.rule_id == source_rule_id, RuleSync.sync_rule_id == target_rule_id)
                await s.execute(stmt)
                await s.commit()
                await event.answer(f"已取消同步规则 {target_rule_id}")
            else:
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
