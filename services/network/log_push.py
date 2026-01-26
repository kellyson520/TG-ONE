import asyncio
import logging
import os
import httpx
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class TelegramPushHandler(logging.Handler):
    """使用 httpx 异步推送告警到 Telegram"""

    TG_API = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        bot_token: str,
        chat_id: str | int,
        level: int = logging.ERROR,
        timeout: float = 5.0,
    ) -> None:
        super().__init__(level=level)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self._loop = None

    def emit(self, record: logging.LogRecord) -> None:
        if not self.bot_token or not self.chat_id:
            return
        
        try:
            text = self._format_text(record)
            url = self.TG_API.format(token=self.bot_token)
            data = {
                "chat_id": str(self.chat_id),
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            
            # 尝试获取运行中的事件循环
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._async_post(url, data))
            except RuntimeError:
                # 不在事件循环中，可能是启动阶段或独立脚本
                # 这里暂时回退到同步请求（或者使用单独的线程，但为了彻底异步化，我们推荐在主循环启动后使用）
                import threading
                threading.Thread(target=self._sync_post, args=(url, data), daemon=True).start()
                
        except Exception:
            pass

    def _format_text(self, record: logging.LogRecord) -> str:
        level_icon = {
            "CRITICAL": "🛑",
            "ERROR": "❌",
            "WARNING": "⚠️",
            "INFO": "ℹ️",
            "DEBUG": "🐞",
        }.get(record.levelname, "📣")
        
        cid = getattr(record, "correlation_id", None)
        # 获取 Trace ID (如果存在于 trace_id_var)
        try:
            from utils.core.log_config import trace_id_var
            cid = cid or trace_id_var.get()
        except ImportError:
            pass

        head = f"{level_icon} <b>{record.levelname}</b> | <code>{record.name}</code>"
        body = self.format(record)
        # HTML 转义，防止标签冲突
        import html
        body = html.escape(body)
        
        tail = f"\n关联ID: {cid}" if cid else ""
        return f"{head}\n<pre>{body}</pre>{tail}"

    async def _async_post(self, url: str, data: Dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(url, data=data)
        except Exception as e:
            # 内部错误不再吐给 logger，防止死循环
            pass

    def _sync_post(self, url: str, data: Dict[str, Any]) -> None:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                client.post(url, data=data)
        except Exception:
            pass


def install_log_push_handlers(root_logger: logging.Logger) -> None:
    """按 env 安装统一日志推送。"""
    tg_enable = os.getenv("LOG_PUSH_TG_ENABLE", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not tg_enable:
        return

    bot_token = os.getenv("LOG_PUSH_TG_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    chat_id = os.getenv("LOG_PUSH_TG_CHAT_ID") or os.getenv("USER_ID")
    level_name = os.getenv("LOG_PUSH_TG_LEVEL", "ERROR").upper()
    level = getattr(logging, level_name, logging.ERROR)

    if not bot_token or not chat_id:
        logger.warning("Log Push enabled but BOT_TOKEN or USER_ID is missing")
        return

    try:
        handler = TelegramPushHandler(bot_token=bot_token, chat_id=chat_id, level=level)
        # 设置格式化程序，因为 Handler 需要它进行 self.format(record)
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        logger.info(f"Telegram Log Push Handler installed (Level: {level_name})")
    except Exception as e:
        logger.error(f"Failed to install Telegram Log Push Handler: {e}")
