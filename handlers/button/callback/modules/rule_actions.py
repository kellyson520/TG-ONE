import logging
from sqlalchemy import text
from utils.processing.auto_delete import respond_and_delete
from core.helpers.common import check_and_clean_chats
from models.models import ForwardRule
from core.container import container

logger = logging.getLogger(__name__)

async def callback_delete(event, rule_id, session, message, data):
    """处理删除规则的回调"""
    async def _do(s):
        rule = await s.get(ForwardRule, int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        try:
            rule_obj = rule
            # 删除关联数据
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
