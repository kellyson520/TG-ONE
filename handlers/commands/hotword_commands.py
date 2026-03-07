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

        subcommand = args[0].lower()
        
        # --- 子命令处理 ---
        
        if subcommand == "add":
            if len(args) < 2:
                await respond_and_delete(event, "❌ 用法: /hot add <词>", delete_after_seconds=5)
                return
            word = args[1].strip()
            success = await hotword_service.add_noise_word(word)
            if success:
                await respond_and_delete(event, f"✅ 已将 '{word}' 加入垃圾库。", delete_after_seconds=5)
            else:
                await respond_and_delete(event, "❌ 添加失败，请检查日志。", delete_after_seconds=5)
            return

        if subcommand in ["del", "delete", "remove"]:
            if len(args) < 2:
                await respond_and_delete(event, "❌ 用法: /hot del <词>", delete_after_seconds=5)
                return
            word = args[1].strip()
            success = await hotword_service.remove_noise_word(word)
            if success:
                await respond_and_delete(event, f"✅ 已从垃圾库移除 '{word}'。", delete_after_seconds=5)
            else:
                await respond_and_delete(event, "❌ 移除失败（可能该词不在垃圾库中）。", delete_after_seconds=5)
            return

        if subcommand in ["page", "list"]:
            page_num = 1
            if len(args) > 1:
                try:
                    page_num = int(args[1])
                except ValueError:
                    page_num = 1
            
            data = await hotword_service.get_noise_list(page=page_num)
            result = hotword_renderer.render_noise_list(data)
            await respond_and_delete(event, result.text, buttons=result.buttons)
            return

        # --- 原有搜索逻辑 ---
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
        logger.error(f"Hotword cmd error: {e}", exc_info=True)
        await respond_and_delete(event, f"❌ 热词操作出错: {str(e)}", delete_after_seconds=5)
