"""转发并发队列与限流管理

为同一 源→目标 会话 提供串行化队列，以及按目标会话的并发上限控制，
避免并发竞争导致的限流与重复发送。
现在已扩展支持通用的 send_message 和 send_file 操作。
"""

from __future__ import annotations

import random
import logging
import os
import asyncio
import time
from typing import Any, Iterable, List, Optional, Union, Callable, Awaitable
from utils.network.circuit_breaker import CircuitBreaker, CircuitOpenException
from utils.network.backpressure import AdaptiveBackpressure

logger = logging.getLogger(__name__)


class FloodWaitException(Exception):
    """FloodWait异常，用于表示Telegram API限流"""

    def __init__(self, seconds: int):
        self.seconds = seconds
        super().__init__(f"FloodWait for {seconds} seconds")


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except Exception:
        return default


class _PerKeySemaphore:
    def __init__(self, default_limit: int) -> None:
        self._limit_default = max(1, int(default_limit))
        self._key_to_sem: dict[str, asyncio.Semaphore] = {}
        # 新增：记录最后访问时间
        self._last_access: dict[str, float] = {}
        self._cleanup_counter = 0

    def acquire(self, key: str):
        now = time.time()
        # 更新访问时间
        self._last_access[key] = now

        # ✅ 优化：概率性触发清理 (每 100 次调用检查一次)
        self._cleanup_counter = (self._cleanup_counter + 1) % 100
        if self._cleanup_counter == 0:
            self._prune_stale_semaphores(now)

        sem = self._key_to_sem.get(key)
        if sem is None:
            sem = asyncio.Semaphore(self._limit_default)
            self._key_to_sem[key] = sem
        return _AsyncReleaser(sem)

    def _prune_stale_semaphores(self, now: float):
        # 移除 1 小时未使用的信号量
        ttl = 3600
        keys_to_remove = [
            k for k, last_ts in self._last_access.items() if now - last_ts > ttl
        ]
        if keys_to_remove:
            logger.debug(f"清理过期信号量: {len(keys_to_remove)} 个")
            for k in keys_to_remove:
                # 只有当信号量未被锁定时才安全移除（虽然 Python GC 会处理，但显式清理更安全）
                sem = self._key_to_sem.get(k)
                if sem and not sem.locked():
                    self._key_to_sem.pop(k, None)
                    self._last_access.pop(k, None)


class _AsyncReleaser:
    def __init__(self, sem: asyncio.Semaphore) -> None:
        self._sem = sem

    async def __aenter__(self):
        await self._sem.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            self._sem.release()
        except Exception:
            pass


# 全局并发上限（可用于保护整体速率）
_GLOBAL_LIMIT = _int_env("FORWARD_MAX_CONCURRENCY_GLOBAL", 50) # Def 50 for max, Backpressure will lower it
_global_sem = asyncio.Semaphore(_GLOBAL_LIMIT)
_current_global_concurrency = 0 # Track active requests for dynamic limiting

# 目标会话并发上限
_TARGET_LIMIT = _int_env("FORWARD_MAX_CONCURRENCY_PER_TARGET", 2)
_target_sem_mgr = _PerKeySemaphore(_TARGET_LIMIT)

# 源→目标对并发上限（同一对强制串行，默认1）
_PAIR_LIMIT = _int_env("FORWARD_MAX_CONCURRENCY_PER_PAIR", 1)
_pair_sem_mgr = _PerKeySemaphore(_PAIR_LIMIT)


# FloodWait 观测（每目标会话的动态冷却时间戳）
_flood_wait_until: dict[str, float] = {}

# 全局 Telegram API 熔断器 (防止整个账号被限流)
_telegram_breaker = CircuitBreaker(
    name="telegram_api_global",
    failure_threshold=10,
    recovery_timeout=60.0
)


# 发送节流：全局/目标/源-目标最小间隔（毫秒）
def _int_env_nonneg(name: str, default: int) -> int:
    try:
        v = int(os.getenv(name, str(default)))
        return max(0, v)
    except Exception:
        return default


_GLOBAL_MIN_INTERVAL_MS = _int_env_nonneg("FORWARD_GLOBAL_MIN_INTERVAL_MS", 0)
_TARGET_MIN_INTERVAL_MS = _int_env_nonneg("FORWARD_TARGET_MIN_INTERVAL_MS", 250)
_PAIR_MIN_INTERVAL_MS = _int_env_nonneg("FORWARD_PAIR_MIN_INTERVAL_MS", 100)

_PACE_JITTER = float(os.getenv("FORWARD_PACING_JITTER", "0.2"))  # ±20% 抖动

_global_next_at: float = 0.0
_target_next_at: dict[str, float] = {}
_pair_next_at: dict[str, float] = {}


def _with_jitter(base_seconds: float) -> float:
    if _PACE_JITTER <= 0:
        return base_seconds
    low = max(0.0, base_seconds * (1.0 - _PACE_JITTER))
    high = base_seconds * (1.0 + _PACE_JITTER)
    return random.uniform(low, high)



class _BackpressureAwareReleaser:
    def __init__(self, sem: asyncio.Semaphore) -> None:
        self._sem = sem

    async def __aenter__(self):
        global _current_global_concurrency
        backpressure = AdaptiveBackpressure.get_instance()
        
        # 1. Backpressure Check (Dynamic)
        while True:
            dynamic_limit = backpressure.concurrency_limit
            if _current_global_concurrency < dynamic_limit:
                break
            await asyncio.sleep(0.5)
            
        _current_global_concurrency += 1
        
        # 2. Semaphore Acquire (Static Hard Limit)
        await self._sem.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        global _current_global_concurrency
        try:
            self._sem.release()
        finally:
            _current_global_concurrency -= 1

async def _run_guarded_operation(
    target_chat_id: Union[int, str],
    source_chat_id: Optional[Union[int, str]],
    operation_name: str,
    func: Callable[[], Awaitable[Any]],
    handle_flood_wait_sleep: bool = True
) -> Any:
    """内部通用限流执行器，处理锁获取、速率控制、指数退避和 FloodWait"""
    global _global_next_at
    
    target_key = str(target_chat_id)
    # 如果没有 source，使用 dummy 值，这样就不会互相阻塞（除非 target 相同）
    # 但如果是 bot 发送，通常我们希望 per-target 串行即可，per-pair 意义不大（因为 source 总是 bot）
    pair_key = f"{source_chat_id}->{target_chat_id}" if source_chat_id else f"bot->{target_chat_id}"

    async def _run_with_retry(
        target_key: str,
        pair_key: str,
        operation_name: str,
        func: Callable[[], Awaitable[Any]]
    ) -> Any:
        global _global_next_at
        
        # 指数退避 + FloodWait 识别
        backoff = [0.0, 0.7, 1.5]
        last_exc: Optional[BaseException] = None
        from utils.helpers.metrics import (
            FORWARD_FLOODWAIT_SECONDS,
            FORWARD_SEND_SECONDS,
        )

        for i, delay in enumerate(backoff):
            if delay > 0:
                try:
                    await asyncio.sleep(delay)
                except Exception:
                    pass
            try:
                # 全局/目标/对 级别的最小间隔控制（加入抖动）
                now = time.time()
                global_wait = max(0.0, _global_next_at - now)
                target_wait = max(
                    0.0, _target_next_at.get(target_key, 0.0) - now
                )
                pair_wait = max(0.0, _pair_next_at.get(pair_key, 0.0) - now)
                wait_time = max(global_wait, target_wait, pair_wait)
                if wait_time > 0:
                    try:
                        await asyncio.sleep(wait_time)
                    except Exception:
                        pass
                
                _start = time.time()
                
                # EXECUTE
                result = await func()
                
                try:
                    FORWARD_SEND_SECONDS.observe(max(0.0, time.time() - _start))
                except Exception:
                    pass
                
                # 成功后更新下一次允许时间
                try:
                    base_now = time.time()
                    if _GLOBAL_MIN_INTERVAL_MS > 0:
                        _global_next_at = base_now + _with_jitter(
                            _GLOBAL_MIN_INTERVAL_MS / 1000.0
                        )
                    if _TARGET_MIN_INTERVAL_MS > 0:
                        _target_next_at[target_key] = base_now + _with_jitter(
                            _TARGET_MIN_INTERVAL_MS / 1000.0
                        )
                    if _PAIR_MIN_INTERVAL_MS > 0:
                        _pair_next_at[pair_key] = base_now + _with_jitter(
                            _PAIR_MIN_INTERVAL_MS / 1000.0
                        )
                except Exception:
                    pass
                    
                return result
                
            except Exception as e:
                last_exc = e
                name = type(e).__name__
                # 识别 Telethon FloodWaitError（尽量通过属性/名称兼容）
                wait_seconds = getattr(e, "seconds", None)
                if wait_seconds is None and "FloodWait" in name:
                    # 兜底解析：从 str(e) 尝试提取秒数
                    try:
                        import re as _re

                        m = _re.search(r"(\d+)", str(e))
                        if m:
                            wait_seconds = int(m.group(1))
                    except Exception:
                        wait_seconds = None
                
                # 特殊字符串解析 (来自 test_flood_wait.py 反馈)
                if wait_seconds is None:
                        try:
                            import re as _re
                            m = _re.search(r"(\d+)\s*s", str(e))
                            if m:
                                wait_seconds = int(m.group(1))
                        except Exception:
                            pass

                if wait_seconds is not None:
                    # FloodWait：记录冷却时间并加抖动
                    jitter = random.uniform(0.8, 1.2)
                    wait = float(wait_seconds) * jitter
                    _flood_wait_until[target_key] = time.time() + wait
                    logger.warning(
                        f"FloodWait: target={target_key} wait={wait_seconds}s (actual {wait:.1f}s)"
                    )
                    try:
                        FORWARD_FLOODWAIT_SECONDS.observe(float(wait_seconds))
                    except Exception:
                        pass
                    # FloodWait：同时推进下一次允许时间（节流），避免紧随其后继续打
                    base_now = time.time() + wait
                    if _GLOBAL_MIN_INTERVAL_MS > 0:
                        _global_next_at = max(_global_next_at, base_now)
                    _target_next_at[target_key] = max(
                        _target_next_at.get(target_key, 0.0), base_now
                    )
                    _pair_next_at[pair_key] = max(
                        _pair_next_at.get(pair_key, 0.0), base_now
                    )
                    # FloodWait 不在本层重试，交由上层重新调度
                    logger.warning(
                        f"触发 FloodWait {wait_seconds}s，释放 Worker 资源"
                    )
                    raise
                else:
                    # 记录但不抛出，进行重试 (backoff loop)
                    if "Batch" in str(e) or "limit" in str(e).lower():
                        # 如果是批量相关的错误，让调用者感知（例如 _forward_messages_batch 需要捕获来降级）
                        # 这里我们仍然重试，但对于某些错误(如 Too Many Requests)可能很快失败
                        pass
                        
                    logger.warning(
                        f"{operation_name} 失败({i+1}/{len(backoff)}) pair={pair_key}: {e}"
                    )
                    continue
        if last_exc:
            raise last_exc

    # 统一的获取顺序：global -> target -> pair，避免死锁
    async with _BackpressureAwareReleaser(_global_sem):
        async with _target_sem_mgr.acquire(target_key):
            async with _pair_sem_mgr.acquire(pair_key):
                # FloodWait 冷却（如果记录尚在生效）
                if handle_flood_wait_sleep:
                    now = time.time()
                    until = _flood_wait_until.get(target_key, 0.0)
                    if now < until:
                        wait = max(0.0, until - now)
                        try:
                            await asyncio.sleep(wait)
                        except Exception:
                            pass
                
                # 接入熔断器保护
                try:
                    return await _telegram_breaker.call(
                        _run_with_retry, 
                        target_key, 
                        pair_key, 
                        operation_name, 
                        func
                    )
                except CircuitOpenException:
                    logger.error(f"Telegram API 处于熔断状态，取消操作: {operation_name}")
                    raise
                except Exception:
                    # _run_with_retry 已经抛出了最终异常
                    raise


async def send_message_queued(
    client: Any,
    target_chat_id: Union[int, str],
    message: str,
    extra_keywords: Optional[dict] = None,
    **kwargs
) -> Any:
    """限流保护的 send_message
    
    Args:
        client: Telethon client
        target_chat_id: 目标聊天ID
        message: 文本内容
        extra_keywords: 日志用的额外信息
        **kwargs: 传递给 send_message 的参数 (如 buttons, reply_to, etc)
    """
    
    async def _send():
        return await client.send_message(target_chat_id, message, **kwargs)

    return await _run_guarded_operation(
        target_chat_id=target_chat_id,
        source_chat_id=None, # Copy mode, source is irrelevant for pair locking usually
        operation_name="SendMsg",
        func=_send
    )


async def send_file_queued(
    client: Any,
    target_chat_id: Union[int, str],
    file: Union[Any, List[Any]],
    caption: Optional[str] = None,
    extra_keywords: Optional[dict] = None,
    **kwargs
) -> Any:
    """限流保护的 send_file (支持单文件或媒体组)
    
    Args:
        client: Telethon client
        target_chat_id: 目标聊天ID
        file: 文件对象或列表
        caption: 说明文字
        extra_keywords: 日志用的额外信息
        **kwargs: 传递给 send_file 的参数
    """
    
    async def _send():
        return await client.send_file(
            target_chat_id, 
            file, 
            caption=caption,
            **kwargs
        )

    return await _run_guarded_operation(
        target_chat_id=target_chat_id,
        source_chat_id=None,
        operation_name="SendFile",
        func=_send
    )

async def get_messages_queued(
    client: Any,
    entity: Union[int, str],
    ids: Optional[Union[int, List[int]]] = None,
    limit: Optional[int] = None,
    **kwargs
) -> Any:
    """限流保护的 get_messages
    
    Args:
        client: Telethon client
        entity: 目标聊天/频道
        ids: 消息ID列表
        limit: 获取数量
        **kwargs: 其他参数
    """
    
    async def _get():
        return await client.get_messages(entity, ids=ids, limit=limit, **kwargs)

    # 对于读取操作，我们也使用 _run_guarded_operation 来防止对同一目标的并发轰炸
    # 同时也享受全局熔断器的保护
    return await _run_guarded_operation(
        target_chat_id=entity if isinstance(entity, (int, str)) else 0, # 如果 entity 是对象，可能需要处理，这里简单处理
        source_chat_id=None,
        operation_name="GetMsg",
        func=_get
    )

async def forward_messages_queued(
    client: Any,
    *,
    source_chat_id: Union[int, str],
    target_chat_id: Union[int, str],
    messages: Union[int, Iterable[int], List[int]],
    from_peer: Optional[Union[int, str]] = None,
    entity: Optional[Union[int, str]] = None,
    extra_kwargs: Optional[dict] = None,
    use_batch_api: bool = True,
    handle_flood_wait_sleep: bool = True,
):
    """带并发队列/限流保护的 forward_messages 调用。"""
    
    # 处理消息列表
    if isinstance(messages, int):
        message_list = [messages]
    elif hasattr(messages, "__iter__"):
        message_list = list(messages)
    else:
        message_list = [messages]

    # 检查是否应该使用批量API
    should_use_batch = (
        use_batch_api
        and len(message_list) > 1
        and _should_use_batch_forward(len(message_list))
    )

    if should_use_batch:
        logger.info(f"使用批量转发API: {len(message_list)} 条消息")
        return await _forward_messages_batch(
            client,
            source_chat_id,
            target_chat_id,
            message_list,
            from_peer,
            entity,
            extra_kwargs,
            handle_flood_wait_sleep,
        )

    # 使用传统单条转发
    kwargs = dict(extra_kwargs or {})
    if entity is not None:
        kwargs["entity"] = entity
    else:
        kwargs["entity"] = target_chat_id

    if "message_thread_id" in kwargs:
        thread_id = kwargs.pop("message_thread_id")
        if thread_id:
             kwargs["top_msg_id"] = thread_id

    kwargs["messages"] = messages
    if from_peer is not None:
        kwargs["from_peer"] = from_peer
    else:
        kwargs["from_peer"] = source_chat_id

    async def _forward():
        return await client.forward_messages(**kwargs)

    return await _run_guarded_operation(
        target_chat_id=target_chat_id,
        source_chat_id=source_chat_id,
        operation_name="Forward",
        func=_forward,
        handle_flood_wait_sleep=handle_flood_wait_sleep
    )


def _should_use_batch_forward(message_count: int) -> bool:
    """判断是否应该使用批量转发API"""
    batch_enabled = os.getenv("FORWARD_ENABLE_BATCH_API", "true").lower() in {
        "true",
        "1",
        "yes",
    }
    max_batch_size = int(os.getenv("FORWARD_MAX_BATCH_SIZE", "50"))

    return batch_enabled and 1 < message_count <= min(max_batch_size, 100)


async def _forward_messages_batch(
    client: Any,
    source_chat_id: Union[int, str],
    target_chat_id: Union[int, str],
    message_ids: List[int],
    from_peer: Optional[Union[int, str]] = None,
    entity: Optional[Union[int, str]] = None,
    extra_kwargs: Optional[dict] = None,
    handle_flood_wait_sleep: bool = True,
):
    """使用批量API转发消息"""
    try:
        from utils.network.telegram_api_optimizer import api_optimizer

        async def _batch_forward():
            return await api_optimizer.forward_messages_batch(
                client,
                from_peer=from_peer or source_chat_id,
                to_peer=entity or target_chat_id,
                message_ids=message_ids,
                silent=(
                    extra_kwargs.get("silent", False)
                    if extra_kwargs
                    else False
                ),
                background=(
                    extra_kwargs.get("background", False)
                    if extra_kwargs
                    else False
                ),
            )
            
        result = await _run_guarded_operation(
            target_chat_id=target_chat_id,
            source_chat_id=source_chat_id,
            operation_name="BatchForward",
            func=_batch_forward,
            handle_flood_wait_sleep=handle_flood_wait_sleep
        )
        
        logger.info(f"批量转发成功: {len(message_ids)} 条消息")
        return result

    except Exception as e:
        logger.error(f"批量转发失败，回退到单条转发: {str(e)}")
        # 回退到单条转发
        results = []
        for msg_id in message_ids:
            try:
                result = await forward_messages_queued(
                    client,
                    source_chat_id=source_chat_id,
                    target_chat_id=target_chat_id,
                    messages=msg_id,
                    from_peer=from_peer,
                    entity=entity,
                    extra_kwargs=extra_kwargs,
                    use_batch_api=False,  # 避免递归
                    handle_flood_wait_sleep=True,
                )
                results.append(result)
            except Exception as single_error:
                logger.error(f"单条转发失败: {single_error}")
                continue
        return results
