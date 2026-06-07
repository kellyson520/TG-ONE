import asyncio
import logging
import random
from typing import Any, Callable, Awaitable, Dict, Tuple
from collections import defaultdict, OrderedDict
from core.exceptions import TransientError
from services.network.pid import PIDController
from services.network.circuit_breaker import CircuitBreaker, CircuitOpenException
import time

logger = logging.getLogger(__name__)

# 全局限流状态记录，供测试和监控使用
_flood_wait_until = {}


def _is_retryable_telegram_operation_error(error: Exception) -> bool:
    if isinstance(error, (TransientError, TimeoutError, ConnectionError)):
        return True

    try:
        from telethon.errors import RPCError, RpcCallFailError, ServerError
    except ImportError:
        RPCError = None
        retryable_rpc_error_types = ()
    else:
        retryable_rpc_error_types = (RpcCallFailError, ServerError)

    if retryable_rpc_error_types and isinstance(error, retryable_rpc_error_types):
        return True

    if RPCError and isinstance(error, RPCError):
        try:
            return int(getattr(error, "code", 0) or 0) >= 500
        except (TypeError, ValueError):
            return False

    return False


def _raise_retry_exhausted(operation_name: str, error: Exception) -> None:
    if isinstance(error, TransientError):
        raise error

    if _is_retryable_telegram_operation_error(error):
        raise TransientError(f"{operation_name} failed after retries: {error}") from error

    raise error

class FloodWaitException(Exception):
    """Telegram FloodWait 异常的统一包装"""
    def __init__(self, seconds):
        self.seconds = seconds
        super().__init__(f"Flood wait for {seconds} seconds required")

class MessageQueueService:
    """
    QoS 4.0 Implements a Multi-Lane Priority Queue system with Traffic Shaping.
    
    Lanes:
    - CRITICAL (P > 90): Admin commands, System signals. 100% Guaranteed.
    - FAST (P >= 50): VIP Groups, Normal Traffic. 70% Share.
    - STANDARD (P < 50): Bulk, Spam, Backlog. 30% Share + Shedding.
    
    Features:
    - Dynamic Routing (CAP Algorithm)
    - Strict Priority Dispatch (Event-Based)
    - Isolation & Anti-Starvation
    """
    
    LANE_CRITICAL = 'critical'
    LANE_FAST = 'fast'
    LANE_STANDARD = 'standard'
    
    # Congestion Penalty Factor for CAP Algorithm
    # Score = Base - (Pending * Factor)
    CONGESTION_PENALTY_FACTOR = 0.5 
    
    def __init__(self, max_size: int = 1000, workers: int = 5):
        # [Phase 1: Multi-Lane Infrastructure]
        self.lanes: Dict[str, asyncio.Queue] = {
            self.LANE_CRITICAL: asyncio.Queue(maxsize=max_size),
            self.LANE_FAST: asyncio.Queue(maxsize=max_size),
            self.LANE_STANDARD: asyncio.Queue(maxsize=max_size)
        }
        self.lane_priority = [self.LANE_CRITICAL, self.LANE_FAST, self.LANE_STANDARD]
        
        self.pending_counts: Dict[int, int] = defaultdict(int)
        self._newItemEvent = asyncio.Event()
        
        self.workers = workers
        self._worker_tasks = []
        self._requeue_tasks = set()
        self._processor_callback: Callable[[Any], Awaitable[None]] = None
        self._started = False
        
        # [Phase 2] PID 控制器用于动态调整处理延迟
        # 目标：保持队列在 10% 负载，避免资源空转或极端背压
        self.pid = PIDController(Kp=0.0001, Ki=0.00001, Kd=0.00005, setpoint=max_size * 0.1)
        self.pid.set_output_limits(0.01, 2.0) # 10ms ~ 2s
        self._current_delay = 0.1

    def set_processor(self, callback: Callable[[Any], Awaitable[None]]):
        """Sets the callback function that will processing messages from the queue."""
        self._processor_callback = callback

    def qsize(self) -> int:
        """Return the approximate size of the queue (sum of all lanes)."""
        return sum(q.qsize() for q in self.lanes.values())
        
    def empty(self) -> bool:
        return all(q.empty() for q in self.lanes.values())

    async def start(self):
        """Starts the worker pool."""
        if self._started:
            return
        
        if not self._processor_callback:
            raise RuntimeError("Processor callback must be set before starting MessageQueueService")

        max_s = self.lanes[self.LANE_STANDARD].maxsize
        logger.info(f"正在启动 MessageQueueService (QoS 4.0)，包含 {self.workers} 个工作线程 (Lanes: {list(self.lanes.keys())}, MaxSize: {max_s})")
        for i in range(self.workers):
            task = asyncio.create_task(self._worker_loop(i))
            self._worker_tasks.append(task)
        self._started = True

    async def stop(self):
        """Gracefully stops the service."""
        logger.info("正在停止 MessageQueueService... 正在等待队列清空")
        while True:
            for lane in self.lanes.values():
                await lane.join()

            pending_requeues = list(self._requeue_tasks)
            if not pending_requeues:
                break
            await asyncio.gather(*pending_requeues, return_exceptions=True)
        
        logger.info("队列已清空。正在取消工作线程")
        for task in self._worker_tasks:
            task.cancel()
        
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._started = False
        logger.info("MessageQueueService 已停止")

    async def enqueue(self, item: Any):
        """
        Producer: Puts an item into the queue.
        Routes item to specific lane based on CAP Algorithm.
        """
        try:
            # 1. Parse Metadata for Routing
            priority = 0
            chat_id = 0
            
            # Unpack (Action, Payload, Priority) tuple
            if isinstance(item, tuple) and len(item) >= 3:
                priority = item[2]
                payload = item[1]
                if isinstance(payload, dict):
                    chat_id = payload.get('chat_id', 0)
                elif hasattr(payload, 'chat_id'):
                    chat_id = getattr(payload, 'chat_id', 0)
            
            # 2. CAP Algorithm (Congestion-Aware Priority)
            # Score = Base - (Pending * Factor)
            current_pending = self.pending_counts[chat_id]
            score = priority - (current_pending * self.CONGESTION_PENALTY_FACTOR)
            
            # 3. Dynamic Routing
            target_lane = self.LANE_STANDARD
            if score >= 90:
                target_lane = self.LANE_CRITICAL
            elif score >= 50:
                target_lane = self.LANE_FAST
            # else STANDARD
            
            # 4. Enqueue
            queue = self.lanes[target_lane]
            
            # Backpressure Check
            if queue.full():
                logger.warning(f"泳道 [{target_lane}] 已满！正在应用背压 (Score={score}, ChatID={chat_id}, Pending={current_pending})")
            
            await queue.put(item)
            
            # 5. Update State
            self.pending_counts[chat_id] += 1
            self._newItemEvent.set()
            
        except Exception as e:
            logger.error(f"Failed to enqueue item: {e}")
            raise

    async def _requeue_batch(self, items):
        for item in items:
            await self.enqueue(item)

    def _schedule_requeue_batch(self, items):
        if not items:
            return
        task = asyncio.create_task(self._requeue_batch(items))
        self._requeue_tasks.add(task)
        task.add_done_callback(self._requeue_tasks.discard)

    def _fill_batch_from_lane(self, lane_name, q, buffer, batch_size):
        """Drain extra items from the selected lane into the current batch."""
        try:
            while len(buffer) < batch_size and not q.empty():
                buffer.append(q.get_nowait())
        except asyncio.QueueEmpty:
            logger.debug(
                "MessageQueueService lane became empty during batch drain: "
                "lane=%s buffered=%s",
                lane_name,
                len(buffer),
            )
        except Exception as e:
            logger.warning(
                "MessageQueueService batch drain failed: lane=%s buffered=%s error=%s",
                lane_name,
                len(buffer),
                e,
            )

    async def _worker_loop(self, worker_id: int):
        """Consumer process with Strict Priority Logic (Event-Based)."""
        logger.debug(f"Worker-{worker_id} started (QoS 4.0).")
        BATCH_SIZE = 100 # Batching within same lane
        buffer = []
        
        while True:
            try:
                # 1. Wait for signal (Zero CPU Idle)
                await self._newItemEvent.wait()
                
                # Check for lanes (Strict Priority: Critical -> Fast -> Standard)
                # We keep looping while ANY lane has items
                while True:
                    selected_lane = None
                    selected_item = None
                    
                    # Strict Priority Scan
                    for lane_name in self.lane_priority:
                        q = self.lanes[lane_name]
                        if not q.empty():
                            try:
                                selected_item = q.get_nowait()
                                selected_lane = lane_name
                                break
                            except asyncio.QueueEmpty:
                                continue
                    
                    if selected_lane is None:
                        # All lanes empty
                        self._newItemEvent.clear()
                        # Double check to avoid race condition where item added just before clear
                        if self.qsize() > 0:
                             self._newItemEvent.set()
                             continue
                        break # Go back to wait()
                    
                    # Found an item!
                    buffer.append(selected_item)
                    
                    # Batching Optimization (Same Lane Only)
                    # Grab more from the SAME lane to batch process
                    q = self.lanes[selected_lane]
                    self._fill_batch_from_lane(selected_lane, q, buffer, BATCH_SIZE)
                        
                    # Process Batch
                    retry_items = []
                    try:
                        await self._processor_callback(buffer)
                    except Exception as e:
                        logger.error(f"Worker-{worker_id} failed to process batch: {e}", exc_info=True)
                        retry_items = list(buffer)
                    finally:
                        # Cleanup & State Update
                        for item in buffer:
                            # Decrement Pending Count
                            cid = 0
                            if isinstance(item, tuple) and len(item) >= 2:
                                payload = item[1]
                                if isinstance(payload, dict): cid = payload.get('chat_id', 0)
                                elif hasattr(payload, 'chat_id'): cid = getattr(payload, 'chat_id', 0)
                            
                            if cid in self.pending_counts:
                                self.pending_counts[cid] = max(0, self.pending_counts[cid] - 1)
                                if self.pending_counts[cid] == 0:
                                    del self.pending_counts[cid] # Cleanup memory
                                    
                            # Mark Task Done
                            self.lanes[selected_lane].task_done()

                        self._schedule_requeue_batch(retry_items)
                            
                        # [PID Logic]
                        q_deep = self.qsize() # Total size
                        raw_pid = self.pid.update(q_deep)
                        self._current_delay = max(0.001, 1.0 / (abs(raw_pid) * 10 + 1))
                        if q_deep > 800: self._current_delay = 0
                        
                        buffer = []
                        # Yield control briefly to avoid starving event loop if processing is synchronous-heavy
                        # But with pure async, it's fine. 
                        # Using PID delay to pace usage if needed
                        if q_deep > 0 and self._current_delay > 0.01:
                             await asyncio.sleep(self._current_delay)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker-{worker_id} crashed loop: {e}", exc_info=True)
                await asyncio.sleep(1)

from core.config import settings

class TelegramQueueService:
    """Telegram API 限流与并发管理服务"""
    
    def __init__(self):
        self._global_limit = settings.FORWARD_MAX_CONCURRENCY_GLOBAL
        self._global_sem = asyncio.Semaphore(self._global_limit)
        self._target_limit = settings.FORWARD_MAX_CONCURRENCY_PER_TARGET
        self._pair_limit = settings.FORWARD_MAX_CONCURRENCY_PER_PAIR
        self._target_semaphores = OrderedDict()
        self._pair_semaphores = OrderedDict()
        self._flood_wait_until = _flood_wait_until
        self._semaphore_cache_max = getattr(settings, "FORWARD_SEMAPHORE_CACHE_MAX", 5000)
        self._flood_wait_cache_max = getattr(settings, "FLOOD_WAIT_CACHE_MAX", 5000)
        self._global_next_at = 0.0
        self._target_next_at = {}
        self._pair_next_at = {}
        from telethon.errors import MessageIdInvalidError, PeerIdInvalidError, ChatAdminRequiredError
        self._telegram_breaker = CircuitBreaker(
            name="telegram_api_global",
            failure_threshold=10,
            recovery_timeout=60.0,
            ignored_exceptions=(MessageIdInvalidError, PeerIdInvalidError, ChatAdminRequiredError),
        )

    def _get_target_sem(self, target_key: str):
        return self._get_cached_sem(self._target_semaphores, target_key, self._target_limit)

    def _get_pair_sem(self, pair_key: str):
        return self._get_cached_sem(self._pair_semaphores, pair_key, self._pair_limit)

    def _get_cached_sem(self, cache: OrderedDict, key: str, limit: int):
        sem = cache.get(key)
        if sem is not None:
            cache.move_to_end(key)
            return sem

        sem = asyncio.Semaphore(limit)
        cache[key] = sem
        self._trim_semaphore_cache(cache, limit)
        return sem

    def _trim_semaphore_cache(self, cache: OrderedDict, limit: int):
        if len(cache) <= self._semaphore_cache_max:
            return

        for key in list(cache.keys()):
            if len(cache) <= self._semaphore_cache_max:
                break
            sem = cache[key]
            if getattr(sem, "_value", 0) >= limit:
                cache.pop(key, None)

    def _trim_flood_wait_cache(self):
        now = time.time()
        for key, until in list(self._flood_wait_until.items()):
            if until <= now:
                self._flood_wait_until.pop(key, None)

        overflow = len(self._flood_wait_until) - self._flood_wait_cache_max
        if overflow <= 0:
            return

        oldest = sorted(self._flood_wait_until.items(), key=lambda item: item[1])[:overflow]
        for key, _ in oldest:
            self._flood_wait_until.pop(key, None)

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
                    from telethon.errors import FloodWaitError, MessageIdInvalidError, PeerIdInvalidError, ChatAdminRequiredError
                    
                    # 1. 处理 FloodWait (需要等待并重试)
                    seconds = None
                    if isinstance(e, FloodWaitError):
                        seconds = e.seconds
                    else:
                        # 尝试从字符串解析 (针对 Mock 或非标准异常)
                        import re
                        err_str = str(e)
                        match = re.search(r"(?:FloodWait|Flood wait|A wait) (?:of|for) (\d+) seconds", err_str, re.IGNORECASE)
                        if match:
                            seconds = int(match.group(1))
                    
                    if seconds is not None:
                        self._handle_flood_wait(target_key, pair_key, seconds)
                        raise FloodWaitException(seconds)
                    
                    # 2. 处理终端错误 (不应重试)
                    if isinstance(e, (MessageIdInvalidError, PeerIdInvalidError, ChatAdminRequiredError)):
                        logger.warning(f"Terminal Telegram error in {operation_name}: {e}. Skipping retries.")
                        raise e

                    # 3. 其他错误则继续重试（根据 backoff 策略）
                    continue
            if last_exc:
                _raise_retry_exhausted(operation_name, last_exc)
        if handle_flood_wait_sleep:
            await self._sleep_or_raise_flood_wait(target_key)

        async with self._global_sem:
            async with self._get_target_sem(target_key):
                async with self._get_pair_sem(pair_key):
                    if handle_flood_wait_sleep:
                        wait_seconds = self._flood_wait_remaining(target_key)
                        if wait_seconds > 0:
                            raise FloodWaitException(max(1, int(wait_seconds)))
                    try:
                        return await self._telegram_breaker.call(_run_with_retry)
                    except CircuitOpenException as e:
                        raise TransientError(
                            str(e),
                            context={
                                "retry_delay_seconds": self._telegram_breaker.recovery_timeout,
                                "increment_attempts": False,
                            },
                        ) from e

    def _update_next_at(self, target_key, pair_key):
        now = time.time()
        self._global_next_at = now + self._with_pacing_jitter(
            self._pacing_interval_seconds("FORWARD_GLOBAL_MIN_INTERVAL_MS", 10)
        )
        self._target_next_at[target_key] = now + self._with_pacing_jitter(
            self._pacing_interval_seconds("FORWARD_TARGET_MIN_INTERVAL_MS", 250)
        )
        self._pair_next_at[pair_key] = now + self._with_pacing_jitter(
            self._pacing_interval_seconds("FORWARD_PAIR_MIN_INTERVAL_MS", 100)
        )

    def _pacing_interval_seconds(self, setting_name: str, default_ms: float) -> float:
        try:
            interval_ms = float(getattr(settings, setting_name, default_ms) or 0.0)
        except (TypeError, ValueError):
            interval_ms = float(default_ms)
        return max(0.0, interval_ms / 1000.0)

    def _with_pacing_jitter(self, seconds: float) -> float:
        if seconds <= 0:
            return 0.0
        try:
            jitter = float(getattr(settings, "FORWARD_PACING_JITTER", 0.0) or 0.0)
        except (TypeError, ValueError):
            jitter = 0.0
        if jitter <= 0:
            return seconds
        return seconds * random.uniform(max(0.0, 1.0 - jitter), 1.0 + jitter)

    def _flood_wait_remaining(self, target_key: str) -> float:
        return max(0.0, self._flood_wait_until.get(target_key, 0) - time.time())

    async def _sleep_or_raise_flood_wait(self, target_key: str) -> None:
        wait_seconds = self._flood_wait_remaining(target_key)
        if wait_seconds <= 0:
            return
        if wait_seconds > 60:
            # 等待时间过长，不建议在工作线程中直接 sleep，否则会挂起整个 Worker
            logger.warning(f"Target {target_key} is in long FloodWait ({wait_seconds:.1f}s). Skipping sleep and raising.")
            raise FloodWaitException(int(wait_seconds))
        await asyncio.sleep(wait_seconds)

    def _handle_flood_wait(self, target_key, pair_key, seconds):
        import random
        self._trim_flood_wait_cache()
        self._flood_wait_until[target_key] = time.time() + float(seconds) * random.uniform(0.8, 1.2)
        self._trim_flood_wait_cache()

telegram_queue_service = TelegramQueueService()

def _pop_handle_flood_wait_sleep(kwargs: dict) -> bool:
    return bool(kwargs.pop("handle_flood_wait_sleep", True))

def _is_retryable_queue_error(error: Exception) -> bool:
    return isinstance(error, (FloodWaitException, TransientError))

async def send_message_queued(client, target_chat_id, message, **kwargs):
    handle_flood_wait_sleep = _pop_handle_flood_wait_sleep(kwargs)
    return await telegram_queue_service.run_guarded_operation(
        target_chat_id,
        None,
        "SendMsg",
        lambda: client.send_message(target_chat_id, message, **kwargs),
        handle_flood_wait_sleep=handle_flood_wait_sleep,
    )
async def send_file_queued(client, target_chat_id, file, **kwargs):
    handle_flood_wait_sleep = _pop_handle_flood_wait_sleep(kwargs)
    return await telegram_queue_service.run_guarded_operation(
        target_chat_id,
        None,
        "SendFile",
        lambda: client.send_file(target_chat_id, file, **kwargs),
        handle_flood_wait_sleep=handle_flood_wait_sleep,
    )
async def forward_messages_queued(client, source_chat_id, target_chat_id, messages, **kwargs):
    use_batch = settings.ENABLE_BATCH_FORWARD_API
    handle_flood_wait_sleep = _pop_handle_flood_wait_sleep(kwargs)
    
    # 获取消息 ID 列表供批量使用
    if isinstance(messages, int):
        ids = [messages]
    elif hasattr(messages, 'id'):
        ids = [messages.id]
    elif isinstance(messages, list):
        ids = [m.id if hasattr(m, 'id') else m for m in messages]
    else:
        ids = [messages]

    if use_batch and len(ids) > 1:
        from services.network.telegram_api_optimizer import api_optimizer
        try:
            return await telegram_queue_service.run_guarded_operation(
                target_chat_id, source_chat_id, "ForwardBatch", 
                lambda: api_optimizer.forward_messages_batch(client, source_chat_id, target_chat_id, ids, **kwargs),
                handle_flood_wait_sleep=handle_flood_wait_sleep,
            )
        except Exception as e:
            if _is_retryable_queue_error(e):
                raise
            logger.warning(f"Batch forward failed, falling back to individual calls: {e}")
            # Fallback to individual
            results = []
            for msg_id in ids:
                try:
                    res = await telegram_queue_service.run_guarded_operation(
                        target_chat_id, source_chat_id, "ForwardSingle", 
                        lambda m=msg_id: client.forward_messages(target_chat_id, m, from_peer=source_chat_id, **kwargs),
                        handle_flood_wait_sleep=handle_flood_wait_sleep,
                    )
                    results.append(res)
                except Exception as ex:
                    if _is_retryable_queue_error(ex):
                        raise
                    logger.warning(f"Failed to forward message {msg_id} during fallback: {ex}")
            return results

    # 单条转发或不启用批量
    return await telegram_queue_service.run_guarded_operation(
        target_chat_id,
        source_chat_id,
        "Forward",
        lambda: client.forward_messages(target_chat_id, messages, from_peer=source_chat_id, **kwargs),
        handle_flood_wait_sleep=handle_flood_wait_sleep,
    )

async def get_messages_queued(client, chat_id, ids=None, **kwargs):
    """
    带队列控制的消息获取。
    增加了实体自动修复逻辑，防止 'Could not find the input entity' 导致的 ValueError。
    """
    async def _get_msgs_with_recovery():
        try:
            return await client.get_messages(chat_id, ids=ids, **kwargs)
        except ValueError as e:
            # 捕获 Telethon 实体缺失错误
            if "Could not find the input entity" in str(e):
                logger.info(f"Entities cache miss for {chat_id}, attempting to resolve via get_entity...")
                try:
                    # 获取实体详情（会尝试通过 API 获取并更新缓存）
                    await client.get_entity(chat_id)
                    # 再次尝试获取消息
                    return await client.get_messages(chat_id, ids=ids, **kwargs)
                except Exception as ex:
                    logger.error(f"Failed to resolve entity for {chat_id}: {ex}")
                    if _is_retryable_queue_error(ex):
                        raise
                    raise e # 抛出原始的 ValueError
            raise e
        except Exception as e:
            raise e

    return await telegram_queue_service.run_guarded_operation(
        chat_id, None, "GetMsgs", _get_msgs_with_recovery
    )
