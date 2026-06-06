from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from telethon.errors import MessageNotModifiedError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def parse_hotword_view_payload(data: str, extra_data=None) -> tuple[str, str]:
    """Parse hotword_view callback data while allowing ':' inside channel names."""
    channel = "global"
    period = "day"
    valid_periods = {"day", "month", "year", "all"}

    if extra_data:
        channel = extra_data[0] or channel
        if len(extra_data) > 1 and extra_data[1] in valid_periods:
            period = extra_data[1]
        return channel, period

    prefix = "hotword_view:"
    if not data.startswith(prefix):
        return channel, period

    payload = data[len(prefix):]
    if not payload:
        return channel, period

    maybe_channel, sep, maybe_period = payload.rpartition(":")
    if sep and maybe_period in valid_periods:
        return maybe_channel or channel, maybe_period
    return payload, period


@MenuHandlerRegistry.register
class HotwordMenuStrategy(BaseMenuHandler):
    """
    Handles Hotword-related menu actions (MIGRATED from legacy callback_handlers).
    - hotword_main: Show global rankings
    - hotword_global_refresh: Refresh global rankings
    - hotword_view: View specific channel rankings
    - hotword_search_prompt: Show search instruction
    """

    ACTIONS = {
        "hotword_main", "hotword_global_refresh", 
        "hotword_view", "hotword_search_prompt",
        "hotword_noise_page", "hotword_noise_add_prompt"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        from ui.renderers.hotword_renderer import hotword_renderer
        from services.hotword_service import get_hotword_service
        
        hotword_service = get_hotword_service()
        data = kwargs.get("data") or event.data.decode("utf-8")
        extra_data = kwargs.get("extra_data", [])

        if action == "hotword_global_refresh" or action == "hotword_main":
            today = datetime.now().strftime("%Y-%m-%d")
            ranks = await hotword_service.get_rankings(period="day")
            result = hotword_renderer.render_global_rankings(ranks, today)
            try:
                await event.edit(result.text, buttons=result.buttons)
            except MessageNotModifiedError:
                pass
            if action == "hotword_global_refresh":
                await event.answer("🔄 数据已刷新 (若无变化则不更新)")
            else:
                await event.answer()

        elif action == "hotword_search_prompt":
            await event.answer("🔍 请直接发送 /hot <关键词> 进行搜索", alert=True)

        elif action == "hotword_view":
            # Supported formats:
            # 1. hotword_view:channel_name:period (via extra_data)
            # 2. legacy string parse
            channel, period = parse_hotword_view_payload(data, extra_data)
            
            ranks = await hotword_service.get_rankings(channel, period=period)
            result = hotword_renderer.render_channel_rankings(channel, ranks, period)
            try:
                await event.edit(result.text, buttons=result.buttons)
            except MessageNotModifiedError:
                pass
            await event.answer()

        elif action == "hotword_noise_page":
            page = 1
            if extra_data:
                page = int(extra_data[0])
            else:
                parts = data.split(":")
                if len(parts) > 1:
                    page = int(parts[1])
            
            data_list = await hotword_service.get_noise_list(page=page)
            result = hotword_renderer.render_noise_list(data_list)
            try:
                await event.edit(result.text, buttons=result.buttons)
            except MessageNotModifiedError:
                pass
            await event.answer()

        elif action == "hotword_noise_add_prompt":
            from services.session_service import session_manager
            session_manager.set_state(event.sender_id, event.chat_id, "hotword_add_noise")
            await event.answer("请发送要加入垃圾库的词汇，支持多行", alert=True)
