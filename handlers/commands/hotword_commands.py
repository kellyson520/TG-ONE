from core.config import settings
from core.helpers.auto_delete import respond_and_delete
from services.hotword_service import get_hotword_service
from ui.renderers.hotword_renderer import hotword_renderer
import logging
import shlex

logger = logging.getLogger(__name__)

async def handle_hotword_command(event, command):
    hotword_service = get_hotword_service()
    try:
        cmd_text = command.strip()
        if cmd_text.startswith('/'):
            parts = cmd_text.split(None, 1)
            cmd_text = parts[1] if len(parts) > 1 else ""
        args = shlex.split(cmd_text)
        
        if not args:
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            ranks = await hotword_service.get_rankings(period="day")
            result = hotword_renderer.render_global_rankings(ranks, today)
            await respond_and_delete(event, result.text, buttons=result.buttons)
            return

        query = args[0]
        period = "day"
        if len(args) > 1:
            period = args[1].lower()
            if period not in ["day", "month", "year", "all"]: period = "day"

        matches = await hotword_service.fuzzy_match_channel(query)
        if not matches:
             await respond_and_delete(event, f"🔍 未找到与 '{query}' 相关的频道统计。", delete_after_seconds=5)
             return

        if len(matches) > 1:
            result = hotword_renderer.render_search_results(query, matches)
            await respond_and_delete(event, result.text, buttons=result.buttons)
            return
        
        target_channel = matches[0]
        ranks = await hotword_service.get_rankings(target_channel, period=period)
        result = hotword_renderer.render_channel_rankings(target_channel, ranks, period)
        await respond_and_delete(event, result.text, buttons=result.buttons)
    except Exception as e:
        logger.error(f"Hotword cmd error: {e}")
        await respond_and_delete(event, "❌ 热词查询出错。", delete_after_seconds=5)
