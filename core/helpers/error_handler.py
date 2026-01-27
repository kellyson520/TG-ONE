"""
统一的错误处理装饰器
用于消除重复的try-except代码模式，提供标准化的错误处理
"""

import functools
import asyncio
import logging
from typing import Any, Callable, Optional, Type, Union
from telethon.errors import FloodWaitError

from core.context import trace_id_var

logger = logging.getLogger(__name__)

def handle_errors(
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool = False,
    error_message: Optional[str] = None,
    specific_errors: Optional[Union[Type[Exception], tuple]] = None,
):
    """
    统一错误处理装饰器
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                # 检查是否只处理特定异常
                if specific_errors and not isinstance(e, specific_errors):
                    raise

                if log_error:
                    cid = trace_id_var.get()
                    func_logger = logging.getLogger(func.__module__ or __name__)
                    message = error_message or f"{func.__name__} 执行失败"
                    func_logger.error(f"[{cid}] {message}: {str(e)}", exc_info=True)

                if reraise:
                    raise

                return default_return

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if specific_errors and not isinstance(e, specific_errors):
                    raise

                if log_error:
                    cid = trace_id_var.get()
                    func_logger = logging.getLogger(func.__module__ or __name__)
                    message = error_message or f"{func.__name__} 执行失败"
                    func_logger.error(f"[{cid}] {message}: {str(e)}", exc_info=True)

                if reraise:
                    raise

                return default_return

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

def handle_telegram_errors(default_return: Any = None, max_retries: int = 3):
    """
    专门处理Telegram API错误的装饰器
    自动处理FloodWaitError等常见错误
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except FloodWaitError as e:
                    logger.warning(f"触发FloodWaitError，需要等待 {e.seconds} 秒")
                    await asyncio.sleep(e.seconds)
                    retries += 1
                except Exception as e:
                    logger.error(f"Telegram API 执行失败: {str(e)}")
                    return default_return
            return default_return
        return wrapper
    return decorator

def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], tuple] = Exception,
):
    """
    失败自动重试装饰器
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            curr_delay = delay
            for i in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if i == max_retries - 1:
                        raise
                    logger.warning(f"执行 {func.__name__} 失败: {str(e)}, 准备进行第 {i+1} 次重试...")
                    await asyncio.sleep(curr_delay)
                    curr_delay *= backoff

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            curr_delay = delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if i == max_retries - 1:
                        raise
                    logger.warning(f"执行 {func.__name__} 失败: {str(e)}, 准备进行第 {i+1} 次重试...")
                    time.sleep(curr_delay)
                    curr_delay *= backoff

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
def log_execution(
    include_args: bool = False,
    include_result: bool = False,
    level: int = logging.DEBUG,
):
    """
    记录函数执行详情的装饰器
    """

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            cid = trace_id_var.get()
            func_logger = logging.getLogger(func.__module__ or __name__)
            
            import time

            start_time = time.time()
            if include_args:
                func_logger.log(level, f"[{cid}] 开始执行 {func.__name__}, 参数: {args}, {kwargs}")
            else:
                func_logger.log(level, f"[{cid}] 开始执行 {func.__name__}")

            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                if include_result:
                    func_logger.log(
                        level,
                        f"[{cid}] {func.__name__} 执行完成, 耗时: {duration:.2f}ms, 结果: {result}",
                    )
                else:
                    func_logger.log(
                        level, f"[{cid}] {func.__name__} 执行完成, 耗时: {duration:.2f}ms"
                    )
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                func_logger.log(
                    level, f"[{cid}] {func.__name__} 执行异常: {e}, 耗时: {duration:.2f}ms"
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            cid = trace_id_var.get()
            func_logger = logging.getLogger(func.__module__ or __name__)
            
            import time

            start_time = time.time()
            if include_args:
                func_logger.log(level, f"[{cid}] 开始执行 {func.__name__}, 参数: {args}, {kwargs}")
            else:
                func_logger.log(level, f"[{cid}] 开始执行 {func.__name__}")

            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                if include_result:
                    func_logger.log(
                        level,
                        f"[{cid}] {func.__name__} 执行完成, 耗时: {duration:.2f}ms, 结果: {result}",
                    )
                else:
                    func_logger.log(
                        level, f"[{cid}] {func.__name__} 执行完成, 耗时: {duration:.2f}ms"
                    )
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                func_logger.log(
                    level, f"[{cid}] {func.__name__} 执行异常: {e}, 耗时: {duration:.2f}ms"
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
