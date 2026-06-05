import logging
from ui.renderers.hotword_renderer import hotword_renderer
from services.hotword_service import get_hotword_service
from core.helpers.common import is_admin
from datetime import datetime

logger = logging.getLogger(__name__)

async def handle_hotword_callback(event):
    """处理热词相关回调 - 整合策略模式分发"""
    data = event.data.decode("utf-8")
    action = data.split(":")[0]
    
    # 使用新菜单策略分发 (Strategy Pattern)
    from handlers.button.strategies import MenuHandlerRegistry
    if not await MenuHandlerRegistry.dispatch(event, action, data=data):
        logger.warning(f"未知热词指令且策略未命中: {data}")
        await event.answer("未知热词指令", alert=True)
