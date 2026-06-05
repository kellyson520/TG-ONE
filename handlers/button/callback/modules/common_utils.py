import logging

logger = logging.getLogger(__name__)

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
