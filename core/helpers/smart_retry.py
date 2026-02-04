import asyncio
import logging
import random
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)

# Telethon Errors
try:
    from telethon.errors import (
        FloodWaitError, 
        RPCError, 
        ServerInternalError, 
        RpcCallFailError,
        ConnectionError as TelethonConnectionError
    )
except ImportError:
    # Dummy classes for typing if telethon not installed (should not happen in prod)
    class FloodWaitError(Exception): pass
    class RPCError(Exception): pass
    class ServerInternalError(Exception): pass
    class RpcCallFailError(Exception): pass
    class TelethonConnectionError(Exception): pass

class SmartRetryManager:
    """
    智能重试管理器 (Exponential Backoff)
    区分业务错误与网络波动
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def should_retry(self, exception: Exception) -> bool:
        """判定是否应该重试"""
        
        # 1. 必杀错误 (Business Logic) -> 不重试
        # 400 Bad Request, Chat Not Found, Privacy Restricted
        if isinstance(exception, RPCError):
             # 400 Bad Request usually implies logic error or invalid input
             if exception.code == 400:
                 return False
             # 403 Forbidden
             if exception.code == 403:
                 return False
        
        # 2. 网络波动/临时错误 -> 重试
        if isinstance(exception, (
            FloodWaitError,         # Telegram 限流 (420)
            ServerInternalError,    # Telegram 服务端错误 (500)
            RpcCallFailError,       # RPC 调用失败 (502)
            TelethonConnectionError,# 连接错误
            TimeoutError,
            ConnectionError
        )):
            return True
        
        # 3. 其他未知错误
        # 默认不重试，防止逻辑错误导致死循环
        return False

    async def execute(self, func: Callable, *args, **kwargs):
        """执行带有重试机制的函数"""
        attempt = 0
        while True:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                attempt += 1
                
                # 检查是否应该重试
                if attempt > self.max_retries or not self.should_retry(e):
                    raise e
                
                # 计算退避时间 (Exponential Backoff + Jitter)
                delay = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
                delay = delay * (0.5 + random.random()) # Add 50-150% jitter
                
                # 特殊处理 FloodWait
                if isinstance(e, FloodWaitError):
                    wait_time = e.seconds + 1
                    if wait_time > 60:
                        # 如果需要等待太久，这被视为"不可重试"的任务（交给 Worker 队列稍后处理更合适）
                        # 但在这里为了简单起见，如果 < 60秒就等
                        logger.warning(f"FloodWait encountered: waiting {wait_time}s")
                        delay = wait_time
                    else:
                        raise e # 太久了，抛出让上层 Queue 处理

                logger.warning(f"SmartRetry: Attempt {attempt}/{self.max_retries} failed ({type(e).__name__}). Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)

# Simple decorator
def smart_retry(max_retries=3, base_delay=1.0):
    manager = SmartRetryManager(max_retries=max_retries, base_delay=base_delay)
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await manager.execute(func, *args, **kwargs)
        return wrapper
    return decorator

# Global Instance
retry_manager = SmartRetryManager()
