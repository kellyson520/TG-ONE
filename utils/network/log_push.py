import threading

import json
import logging
import os
from typing import Any, Dict

try:
    import requests
except Exception:
    requests = None


class TelegramPushHandler(logging.Handler):
    """使用当前机器人 Token 向指定 chat 发送告警（默认发给 USER_ID）。"""

    TG_API = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        bot_token: str,
        chat_id: str | int,
        level: int = logging.ERROR,
        timeout: float = 3.0,
    ) -> None:
        super().__init__(level=level)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout

    def emit(self, record: logging.LogRecord) -> None:
        if requests is None or not self.bot_token or not self.chat_id:
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
            threading.Thread(target=self._post, args=(url, data), daemon=True).start()
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
        head = f"{level_icon} <b>{record.levelname}</b> | <code>{record.name}</code>"
        body = self.format(record)
        tail = f"\n关联ID: {cid}" if cid else ""
        return head + "\n" + body + tail

    def _post(self, url: str, data: Dict[str, Any]) -> None:
        try:
            requests.post(url, data=data, timeout=self.timeout)
        except Exception:
            pass


def install_log_push_handlers(root_logger: logging.Logger) -> None:
    """按 env 安装统一日志推送（简化版，仅 Telegram）。"""
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
    level = getattr(
        logging, (os.getenv("LOG_PUSH_TG_LEVEL", "ERROR").upper()), logging.ERROR
    )

    if not bot_token or not chat_id:
        return

    try:
        handler = TelegramPushHandler(bot_token=bot_token, chat_id=chat_id, level=level)
        root_logger.addHandler(handler)
    except Exception:
        pass
