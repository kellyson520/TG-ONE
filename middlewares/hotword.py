import asyncio
import logging
from typing import Callable, List, Optional
from core.pipeline import Middleware, MessageContext
from core.config import settings
from services.hotword_service import get_hotword_service

logger = logging.getLogger(__name__)

class HotwordCollectorMiddleware(Middleware):
    def __init__(self, hotword_service):
        super().__init__()
        self.hotword_service = hotword_service
        self.queue = asyncio.Queue(maxsize=1000)
        self.worker_task = None
        
    async def process(self, ctx: MessageContext, _next_call: Callable) -> None:
        if not settings.ENABLE_HOTWORD:
            await _next_call()
            return
            
        text = self._extract_text(ctx)
        if text:
            try:
                from core.helpers.id_utils import get_display_name_async
                channel_name = await get_display_name_async(ctx.chat_id)
                channel_name = channel_name.replace("/", "_").replace("\\", "_")
                # 记录用户 ID，用于可信度计算 (去重)
                # 从消息对象中获取发送者 ID（频道消息可能为 None）
                sender_id = getattr(ctx.message_obj, 'sender_id', None)
                self.queue.put_nowait((channel_name, sender_id, text))
            except asyncio.QueueFull:
                logger.warning("Hotword queue full, dropping message.")
            except Exception as e:
                logger.error(f"Hotword collection failed: {e}")

        await _next_call()

    def _extract_text(self, ctx: MessageContext) -> str:
        msg = ctx.message_obj
        if not msg: return ""
        text_parts = []
        if msg.message: text_parts.append(msg.message)
        if ctx.is_group and ctx.group_messages:
            for g_msg in ctx.group_messages:
                if g_msg.message: text_parts.append(g_msg.message)
        return "\n".join(text_parts).strip()

    async def start_worker(self):
        if self.worker_task: return
        async def _loop():
            buffer = {}
            last_flush = asyncio.get_running_loop().time()
            self.hotword_service.start_monitoring()

            async def _disk_heartbeat():
                while True:
                    await asyncio.sleep(settings.HOTWORD_SYNC_INTERVAL)
                    try: await self.hotword_service.flush_to_disk()
                    except Exception as e:
                        logger.error(f"Hotword disk heartbeat flush failed: {e}")
            asyncio.create_task(_disk_heartbeat())

            while True:
                try:
                    try:
                        channel_name, user_id, text = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                        buffer.setdefault(channel_name, []).append({"uid": user_id, "text": text})
                    except asyncio.TimeoutError: pass
                    
                    now = asyncio.get_event_loop().time()
                    if any(buffer) and (sum(len(v) for v in buffer.values()) >= settings.HOTWORD_BATCH_SIZE or (now - last_flush >= 5.0)):
                        await self.hotword_service.ensure_active()
                        for chan, texts in list(buffer.items()):
                            await self.hotword_service.process_batch(chan, texts)
                        buffer.clear()
                        last_flush = now
                except Exception as e:
                    logger.error(f"Hotword worker error: {e}")
                    await asyncio.sleep(1)

        self.worker_task = asyncio.create_task(_loop())
        logger.info("HotwordCollector initialized.")

_collector_instance = None
def get_hotword_collector() -> HotwordCollectorMiddleware:
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = HotwordCollectorMiddleware(get_hotword_service())
    return _collector_instance
