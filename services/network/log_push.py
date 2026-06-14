import asyncio
import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TelegramPushHandler(logging.Handler):
    """使用 httpx 异步推送告警到 Telegram（复用连接）"""

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
        self._async_client: Optional["httpx.AsyncClient"] = None
        self._sync_client: Optional["httpx.Client"] = None
        self._client_lock = threading.Lock()

    def _get_async_client(self) -> "httpx.AsyncClient":
        """延迟初始化复用的异步客户端"""
        if self._async_client is None or self._async_client.is_closed:
            import httpx as _httpx
            self._async_client = _httpx.AsyncClient(timeout=self.timeout)
        return self._async_client

    def _get_sync_client(self) -> "httpx.Client":
        """延迟初始化复用的同步客户端（线程安全）"""
        with self._client_lock:
            if self._sync_client is None or self._sync_client.is_closed:
                import httpx as _httpx
                self._sync_client = _httpx.Client(timeout=self.timeout)
            return self._sync_client

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

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._async_post(url, data))
            except RuntimeError:
                threading.Thread(
                    target=self._sync_post, args=(url, data), daemon=True
                ).start()

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
        try:
            from core.context import trace_id_var

            cid = cid or trace_id_var.get()
        except ImportError:
            pass

        head = (
            f"{level_icon} <b>{record.levelname}</b> | <code>{record.name}</code>"
        )
        body = self.format(record)
        import html

        body = html.escape(body)

        tail = f"\n关联ID: {cid}" if cid else ""
        return f"{head}\n<pre>{body}</pre>{tail}"

    async def _async_post(self, url: str, data: Dict[str, Any]) -> None:
        try:
            client = self._get_async_client()
            await client.post(url, data=data)
        except Exception:
            # 连接可能已失效，重置
            if self._async_client and not self._async_client.is_closed:
                await self._async_client.aclose()
                self._async_client = None

    def _sync_post(self, url: str, data: Dict[str, Any]) -> None:
        try:
            client = self._get_sync_client()
            client.post(url, data=data)
        except Exception:
            # 连接可能已失效，重置
            with self._client_lock:
                if self._sync_client and not self._sync_client.is_closed:
                    self._sync_client.close()
                    self._sync_client = None

    async def close_async(self) -> None:
        """异步关闭客户端连接"""
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None

    def close(self) -> None:
        """关闭同步客户端连接"""
        with self._client_lock:
            if self._sync_client and not self._sync_client.is_closed:
                self._sync_client.close()
                self._sync_client = None
        super().close()


from core.config import settings


def install_log_push_handlers(root_logger: logging.Logger) -> None:
    """按 settings 安装统一日志推送。"""
    tg_enable = settings.LOG_PUSH_TG_ENABLE
    if not tg_enable:
        return

    bot_token = settings.LOG_PUSH_TG_BOT_TOKEN or settings.BOT_TOKEN
    chat_id = settings.LOG_PUSH_TG_CHAT_ID or settings.USER_ID
    level_name = settings.LOG_PUSH_TG_LEVEL.upper()
    level = getattr(logging, level_name, logging.ERROR)

    if not bot_token or not chat_id:
        logger.warning("Log Push enabled but BOT_TOKEN or USER_ID is missing")
        return

    try:
        handler = TelegramPushHandler(
            bot_token=bot_token, chat_id=chat_id, level=level
        )
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        logger.info(f"Telegram Log Push Handler installed (Level: {level_name})")
    except Exception as e:
        logger.error(f"Failed to install Telegram Log Push Handler: {e}")
