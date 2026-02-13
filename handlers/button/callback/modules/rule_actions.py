import logging
from core.helpers.auto_delete import respond_and_delete
from core.container import container

logger = logging.getLogger(__name__)

async def callback_delete(event, rule_id, session, message, data):
    """处理删除规则的回调 - 使用 Service 层"""
    if not rule_id:
        await event.answer("无效的规则ID", alert=True)
        return

    try:
        rid = int(rule_id)
    except (ValueError, TypeError):
        await event.answer("解析规则ID失败", alert=True)
        return

    try:
        # 使用 Service 层删除规则
        result = await container.rule_service.delete_rule(rid)
        
        if result.get('success'):
            await message.delete()
            await respond_and_delete(event, "✅ 已删除规则")
            await event.answer("已删除规则")
        else:
            await event.answer(f"❌ 删除失败: {result.get('error')}", alert=True)
            
    except Exception as e:
        logger.error(f"删除规则时出错: {str(e)}", exc_info=True)
        await event.answer("⚠️ 删除规则失败", alert=True)
    
    return
