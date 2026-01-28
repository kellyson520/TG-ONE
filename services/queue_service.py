import asyncio
import logging
from typing import Any, Callable, Awaitable
from services.network.pid import PIDController
from services.network.circuit_breaker import CircuitBreaker
import time

logger = logging.getLogger(__name__)

class MessageQueueService:
    """
    Implements a Producer-Consumer pattern with Backpressure using asyncio.Queue.
    Ensures Zero Message Loss by blocking the Producer when the queue is full.
    """
    
    def __init__(self, max_size: int = 1000, workers: int = 5):
        self.queue = asyncio.Queue(maxsize=max_size)
        self.workers = workers
        self._worker_tasks = []
        self._processor_callback: Callable[[Any], Awaitable[None]] = None
        self._started = False
        
        # [Phase 2] PID 控制器用于动态调整处理延迟
        # 目标：保持队列在 10% 负载，避免资源空转或极端背压
        self.pid = PIDController(Kp=0.0001, Ki=0.00001, Kd=0.00005, setpoint=max_size * 0.1)
        # 输出为 sleep 时间，负相关 (负载越高，sleep 越短)
        # 这里我们将 PID 映射到延迟的减量或直接设定延迟
        self.pid.set_output_limits(0.01, 2.0) # 10ms ~ 2s
        self._current_delay = 0.1

    def set_processor(self, callback: Callable[[Any], Awaitable[None]]):
        """Sets the callback function that will process messages from the queue."""
        self._processor_callback = callback

    async def start(self):
        """Starts the worker pool."""
        if self._started:
            return
        
        if not self._processor_callback:
            raise RuntimeError("Processor callback must be set before starting MessageQueueService")

        logger.info(f"Starting MessageQueueService with {self.workers} workers (Queue Size: {self.queue.maxsize})")
        for i in range(self.workers):
            task = asyncio.create_task(self._worker_loop(i))
            self._worker_tasks.append(task)
        self._started = True

    async def stop(self):
        """
        Gracefully stops the service.
        Waits for the queue to drain before cancelling workers.
        """
        logger.info("Stopping MessageQueueService... Waiting for queue to drain.")
        await self.queue.join()  # Wait for all items to be processed
        
        logger.info("Queue drained. Cancelling workers.")
        for task in self._worker_tasks:
            task.cancel()
        
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._started = False
        logger.info("MessageQueueService stopped.")

    async def enqueue(self, item: Any):
        """
        Producer: Puts an item into the queue.
        BLOCKS if the queue is full (Backpressure).
        """
        try:
            # Check if queue is dangerously full
            if self.queue.full():
                logger.warning("MessageQueue is FULL! Applying Backpressure (Blocking Producer).")
            
            await self.queue.put(item)
        except Exception as e:
            logger.error(f"Failed to enqueue item: {e}")
            raise

    async def _worker_loop(self, worker_id: int):
        """Consumer process with Greedy Batching."""
        logger.debug(f"Worker-{worker_id} started.")
        BATCH_SIZE = 100
        buffer = []
        
        while True:
            try:
                # 1. Wait for the first item (Blocking)
                item = await self.queue.get()
                buffer.append(item)
                
                # 2. Greedy fetch: Grab more items if available immediately
                # This ensures high throughput under load
                try:
                    while len(buffer) < BATCH_SIZE and not self.queue.empty():
                        buffer.append(self.queue.get_nowait())
                except asyncio.QueueEmpty:
                    pass
                
                # 3. Process the batch
                try:
                    # Note: Processor must handle List[Any]
                    await self._processor_callback(buffer)
                except Exception as e:
                    logger.error(f"Worker-{worker_id} failed to process batch of {len(buffer)} items: {e}", exc_info=True)
                finally:
                    # 4. Mark all as done
                    for _ in range(len(buffer)):
                        self.queue.task_done()
                    
                    # 5. [PID Control] 动态调整频率
                    # 获取当前队列深度作为反馈
                    q_deep = self.queue.qsize()
                    # 负载越高，PID 应该输出越小的延迟。
                    # 由于我们的 PID update 是 setpoint - feedback，
                    # 这里的 feedback 是 q_deep。如果 q_deep > setpoint, error 为负。
                    # 为了简单控制，我们用一个基准延迟减去 PID 输出，或者直接让 PID 控制延迟。
                    # 这里采取：延迟 = 1.0 / (PID_output_scaled + 1)
                    raw_pid = self.pid.update(q_deep)
                    # 映射：q_deep 越大，raw_pid 越小(负向越深), 导致延迟变小
                    # 简单的反向逻辑
                    self._current_delay = max(0.001, 1.0 / (abs(raw_pid) * 10 + 1))
                    
                    if q_deep > self.queue.maxsize * 0.8:
                        self._current_delay = 0 # 紧急状态，不休眠
                    
                    buffer = []
                    await asyncio.sleep(self._current_delay)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker-{worker_id} crashed loop: {e}", exc_info=True)
                await asyncio.sleep(1) # Prevent busy loop on crash


class TelegramQueueService:
    """Telegram API 限流与并发管理服务"""
    
    def __init__(self):
        import os
        self._global_limit = int(os.getenv("FORWARD_MAX_CONCURRENCY_GLOBAL", "50"))
        self._global_sem = asyncio.Semaphore(self._global_limit)
        self._target_limit = int(os.getenv("FORWARD_MAX_CONCURRENCY_PER_TARGET", "2"))
        self._pair_limit = int(os.getenv("FORWARD_MAX_CONCURRENCY_PER_PAIR", "1"))
        self._target_semaphores = {}
        self._pair_semaphores = {}
        self._flood_wait_until = {}
        self._global_next_at = 0.0
        self._target_next_at = {}
        self._pair_next_at = {}
        self._telegram_breaker = CircuitBreaker(name="telegram_api_global", failure_threshold=10, recovery_timeout=60.0)

    def _get_target_sem(self, target_key: str):
        if target_key not in self._target_semaphores:
            self._target_semaphores[target_key] = asyncio.Semaphore(self._target_limit)
        return self._target_semaphores[target_key]

    def _get_pair_sem(self, pair_key: str):
        if pair_key not in self._pair_semaphores:
            self._pair_semaphores[pair_key] = asyncio.Semaphore(self._pair_limit)
        return self._pair_semaphores[pair_key]

    async def run_guarded_operation(self, target_chat_id, source_chat_id, operation_name, func, handle_flood_wait_sleep=True):
        target_key = str(target_chat_id)
        pair_key = f"{source_chat_id}->{target_chat_id}" if source_chat_id else f"bot->{target_chat_id}"
        async def _run_with_retry():
            backoff = [0.0, 0.7, 1.5]
            last_exc = None
            for delay in backoff:
                if delay > 0: await asyncio.sleep(delay)
                try:
                    now = time.time()
                    wait = max(0, self._global_next_at - now, self._target_next_at.get(target_key, 0) - now, self._pair_next_at.get(pair_key, 0) - now)
                    if wait > 0: await asyncio.sleep(wait)
                    result = await func()
                    self._update_next_at(target_key, pair_key)
                    return result
                except Exception as e:
                    last_exc = e
                    from telethon.errors import FloodWaitError
                    if isinstance(e, FloodWaitError):
                        self._handle_flood_wait(target_key, pair_key, e.seconds)
                        raise
                    continue
            if last_exc:
                raise last_exc
        async with self._global_sem:
            async with self._get_target_sem(target_key):
                async with self._get_pair_sem(pair_key):
                    if handle_flood_wait_sleep:
                        until = self._flood_wait_until.get(target_key, 0)
                        if time.time() < until: await asyncio.sleep(until - time.time())
                    return await self._telegram_breaker.call(_run_with_retry)

    def _update_next_at(self, target_key, pair_key):
        now = time.time()
        self._global_next_at = now + 0.01
        self._target_next_at[target_key] = now + 0.25
        self._pair_next_at[pair_key] = now + 0.1

    def _handle_flood_wait(self, target_key, pair_key, seconds):
        import random
        self._flood_wait_until[target_key] = time.time() + float(seconds) * random.uniform(0.8, 1.2)

telegram_queue_service = TelegramQueueService()
async def send_message_queued(client, target_chat_id, message, **kwargs):
    return await telegram_queue_service.run_guarded_operation(target_chat_id, None, "SendMsg", lambda: client.send_message(target_chat_id, message, **kwargs))
async def send_file_queued(client, target_chat_id, file, **kwargs):
    return await telegram_queue_service.run_guarded_operation(target_chat_id, None, "SendFile", lambda: client.send_file(target_chat_id, file, **kwargs))
async def forward_messages_queued(client, source_chat_id, target_chat_id, messages, **kwargs):
    return await telegram_queue_service.run_guarded_operation(target_chat_id, source_chat_id, "Forward", lambda: client.forward_messages(target_chat_id, messages, from_peer=source_chat_id, **kwargs))
