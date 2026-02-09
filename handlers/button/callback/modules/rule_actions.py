import logging
from sqlalchemy import text
from core.helpers.auto_delete import respond_and_delete
from core.helpers.common import check_and_clean_chats
from models.models import ForwardRule
from core.container import container

logger = logging.getLogger(__name__)

async def callback_delete(event, rule_id, session, message, data):
    """处理删除规则的回调"""
    async with container.db.get_session(session) as s:
        if not rule_id:
            await event.answer("无效的规则ID", alert=True)
            return

        try:
            rid = int(rule_id)
        except (ValueError, TypeError):
            await event.answer("解析规则ID失败", alert=True)
            return

        rule = await s.get(ForwardRule, rid)
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
                from web_admin.rss.api.endpoints.feed import delete_rule_data
                await delete_rule_data(rid)
                logger.info(f"成功删除RSS规则数据: {rule_id}")
            except Exception as e:
                logger.warning(f"删除RSS数据遇到错误 (由于规则已删除，可忽略): {e}")

        except Exception as e:
            # Note: commit/rollback handled by get_session if transaction started, 
            # but we can explicitly rollback here for clarity.
            logger.error(f"删除规则时出错: {str(e)}")
            await event.answer("删除规则失败")
            return

        await check_and_clean_chats(s, rule_obj)
        await message.delete()
        await respond_and_delete(event, ("✅ 已删除规则"))
        await event.answer("已删除规则")
    return
