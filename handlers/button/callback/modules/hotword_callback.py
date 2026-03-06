import logging
from ui.renderers.hotword_renderer import hotword_renderer
from services.hotword_service import get_hotword_service
from core.helpers.common import is_admin
from datetime import datetime

logger = logging.getLogger(__name__)

async def callback_hotword_global(event):
    hotword_service = get_hotword_service()
    today = datetime.now().strftime("%Y-%m-%d")
    ranks = hotword_service.get_rankings(period="day")
    result = hotword_renderer.render_global_rankings(ranks, today)
    await event.edit(result.text, buttons=result.buttons)
    await event.answer("数据已更新")

async def callback_hotword_view(event, channel_id: str, period: str = "day"):
    hotword_service = get_hotword_service()
    ranks = hotword_service.get_rankings(channel_id, period=period)
    result = hotword_renderer.render_channel_rankings(channel_id, ranks, period)
    await event.edit(result.text, buttons=result.buttons)
    await event.answer()

async def callback_hotword_search_prompt(event):
    await event.answer("请直接发送 /hot <关键词> 进行搜索", alert=True)

async def handle_hotword_callback(event):
    data = event.data.decode("utf-8")
    if data == "hotword_global_refresh" or data == "hotword_main":
        await callback_hotword_global(event)
    elif data == "hotword_search_prompt":
        await callback_hotword_search_prompt(event)
    elif data.startswith("hotword_view:"):
        parts = data.split(":")
        channel = parts[1] if len(parts) > 1 else "global"
        period = parts[2] if len(parts) > 2 else "day"
        await callback_hotword_view(event, channel, period)
    else:
        await event.answer("未知热词指令", alert=True)
