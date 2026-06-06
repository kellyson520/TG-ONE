from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from telethon.errors import MessageNotModifiedError
from datetime import datetime
import logging
from ui.hotword_callback_codec import is_hotword_channel_token, resolve_hotword_channel

logger = logging.getLogger(__name__)


def parse_hotword_view_payload(data: str, extra_data=None) -> tuple[str, str]:
    """Parse hotword_view callback data while allowing ':' inside channel names."""
    channel = "global"
    period = "day"
    valid_periods = {"day", "month", "year", "all"}

    if extra_data:
        parts = [str(part) for part in extra_data if part is not None]
        if parts and parts[-1] in valid_periods:
            period = parts.pop()

        is_token_payload = data.startswith("hotword_view_id:") or data.startswith("new_menu:hotword_view_id:")
        if is_token_payload:
            token = parts[0] if parts else ""
            resolved_channel = resolve_hotword_channel(token)
            channel = resolved_channel or token or channel
        elif parts:
            channel = ":".join(parts) or channel
        return channel, period

    token_prefix = "hotword_view_id:"
    if data.startswith(token_prefix):
        payload = data[len(token_prefix):]
        token, sep, maybe_period = payload.rpartition(":")
        if sep and maybe_period in valid_periods:
            period = maybe_period
        else:
            token = payload
        resolved_channel = resolve_hotword_channel(token)
        return resolved_channel or token or channel, period

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
        "hotword_view", "hotword_view_id", "hotword_search_prompt",
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

        elif action in {"hotword_view", "hotword_view_id"}:
            # Supported formats:
            # 1. hotword_view:channel_name:period (via extra_data)
            # 2. legacy string parse
            channel, period = parse_hotword_view_payload(data, extra_data)
            if action == "hotword_view_id" and is_hotword_channel_token(channel):
                channel = await hotword_service.resolve_channel_token(channel) or channel
            
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
