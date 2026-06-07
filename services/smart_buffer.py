import asyncio
import logging
import time
from typing import Dict, List, Any, Callable, Awaitable
from core.config import settings

logger = logging.getLogger(__name__)


class SmartBufferService:
    """
    智能聚合缓冲区 (公交车机制)
    解决连珠炮发图和短时间内多条消息刷屏问题
    """

    def __init__(self):
        # 存储机制:
        # (rule_id, target_chat_id) -> contexts/timer/timestamps/config/future
        self._buffers: Dict[tuple, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._total_contexts = 0  # 监控总消息持荷

    async def push(
        self,
        rule_id: int,
        target_chat_id: int,
        context: Any,
        send_callback: Callable[[List[Any]], Awaitable[None]],
        **kwargs,
    ):
        """
        将消息推入缓冲区
        :param kwargs: 可选参数，覆盖全局设置，如 debounce_time, max_wait_time
        """
        key = (rule_id, target_chat_id)

        # 实时从 settings 获取最新全局配置，确保热更新生效
        # 如果 kwargs 传入了，则以 kwargs 为准（实现按规则自定义）
        config = {
            "enabled": (
                kwargs.get('enabled')
                if kwargs.get('enabled') is not None
                else getattr(settings, 'ENABLE_SMART_BUFFER', True)
            ),
            "debounce": (
                kwargs.get('debounce_time')
                or getattr(settings, 'SMART_BUFFER_DEBOUNCE', 3.5)
            ),
            "max_wait": (
                kwargs.get('max_wait_time')
                or getattr(settings, 'SMART_BUFFER_MAX_WAIT', 8.0)
            ),
            "max_batch": (
                kwargs.get('max_batch_size')
                or getattr(settings, 'SMART_BUFFER_MAX_BATCH', 10)
            ),
        }

        if not config["enabled"]:
            await send_callback([context])
            return

        # 降级熔断防护 (Fast Pass-through) - 防止 OOM
        max_total = getattr(settings, 'MAX_SMART_BUFFER_TOTAL', 2000)
        if self._total_contexts >= max_total:
            # logger.warning 可能在高并发下太吵，可以只打印不刷写
            await send_callback([context])
            return

        flush_now = False
        flush_future = None
        async with self._lock:
            self._total_contexts += 1
            if key not in self._buffers:
                flush_future = asyncio.get_running_loop().create_future()
                self._buffers[key] = {
                    "contexts": [context],
                    "timer": None,
                    "start_time": time.time(),
                    "last_received": time.time(),
                    "config": config,
                    "future": flush_future,
                    "event": asyncio.Event(),
                }
                # 启动发车计时器
                self._buffers[key]["timer"] = asyncio.create_task(
                    self._wait_and_flush(key, send_callback)
                )
                logger.debug(
                    "🚍 [小车启动] 规则 %s -> 目标 %s 开始收集消息 "
                    "(防抖: %ss)",
                    rule_id,
                    target_chat_id,
                    config['debounce'],
                )
            else:
                buffer = self._buffers[key]
                flush_future = buffer.get("future")
                buffer["contexts"].append(context)
                buffer["last_received"] = time.time()
                # 更新配置（以防规则在运行中被修改）
                buffer["config"].update(config)
                event = buffer.get("event")
                if event:
                    event.set()

                # 如果达到最大批次（如10张图），立即触发发车
                if len(buffer["contexts"]) >= buffer["config"]["max_batch"]:
                    logger.debug(
                        "🚀 [满载发车] 规则 %s 积压达 %s 条，立即发出",
                        rule_id,
                        len(buffer['contexts']),
                    )
                    if buffer["timer"]:
                        buffer["timer"].cancel()
                    flush_now = True

        if flush_now:
            try:
                await self._flush(key, send_callback)
            except Exception:
                if flush_future and flush_future.done():
                    flush_future.exception()
                raise
            return

        if flush_future:
            await asyncio.shield(flush_future)

    async def _wait_and_flush(self, key: tuple, send_callback: Callable):
        """计时器逻辑"""
        try:
            while True:
                async with self._lock:
                    buffer = self._buffers.get(key)
                    if not buffer:
                        break

                    now = time.time()
                    elapsed_since_last = now - buffer["last_received"]
                    total_wait = now - buffer["start_time"]
                    config = buffer["config"]

                    debounce_due = elapsed_since_last >= config["debounce"]
                    max_wait_due = total_wait >= config["max_wait"]
                    if debounce_due or max_wait_due:
                        reason = "防抖超时" if debounce_due else "强行发车"
                        count = len(buffer["contexts"])
                        waited = round(total_wait, 1)
                        wait_event = None
                        wait_time = 0
                    else:
                        wait_event = buffer.get("event")
                        if wait_event is None:
                            wait_event = asyncio.Event()
                            buffer["event"] = wait_event

                        debounce_remaining = (
                            config["debounce"] - elapsed_since_last
                        )
                        max_wait_remaining = config["max_wait"] - total_wait
                        wait_time = max(
                            0,
                            min(debounce_remaining, max_wait_remaining),
                        )
                        wait_event.clear()

                if wait_event is None:
                    logger.debug(
                        "🚏 [站点发车] 规则 %s %s，发送 %s 条消息 (已等 %ss)",
                        key[0],
                        reason,
                        count,
                        waited,
                    )
                    await self._flush(key, send_callback)
                    break

                try:
                    await asyncio.wait_for(
                        wait_event.wait(),
                        timeout=wait_time,
                    )
                except asyncio.TimeoutError:
                    logger.debug(
                        "缓冲区计时器等待超时: rule_id=%s, target_chat_id=%s, timeout=%.3fs",
                        key[0],
                        key[1],
                        wait_time,
                    )
        except asyncio.CancelledError:
            logger.debug(
                "缓冲区计时器已取消: rule_id=%s, target_chat_id=%s",
                key[0],
                key[1],
            )
        except Exception as e:
            logger.error(f"缓冲区计时器异常: {e}")
            async with self._lock:
                buffer = self._buffers.pop(key, None)
                if buffer:
                    self._total_contexts = max(
                        0,
                        self._total_contexts
                        - len(buffer.get("contexts") or []),
                    )

    async def _flush(self, key: tuple, send_callback: Callable):
        """执行发送并清理缓冲区"""
        async with self._lock:
            buffer = self._buffers.pop(key, None)
            if not buffer or not buffer["contexts"]:
                return

            contexts = buffer["contexts"]
            flush_future = buffer.get("future")
            self._total_contexts = max(0, self._total_contexts - len(contexts))

        # 在锁外执行回调，避免阻塞新消息推入
        try:
            await send_callback(contexts)
        except Exception as e:
            logger.error(f"缓冲区发送回调失败: {e}")
            if flush_future and not flush_future.done():
                flush_future.set_exception(e)
            raise
        else:
            if flush_future and not flush_future.done():
                flush_future.set_result(None)


# 全局单例
smart_buffer = SmartBufferService()
