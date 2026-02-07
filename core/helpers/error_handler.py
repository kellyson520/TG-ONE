"""
统一的错误处理装饰器
用于消除重复的try-except代码模式，提供标准化的错误处理
"""

import functools
import asyncio
import logging
import inspect
from typing import Any, Optional, Type, Union, Callable, TypeVar, cast
from telethon.errors import FloodWaitError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Callable[..., Any])

def handle_errors(
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool = False,
    error_message: Optional[str] = None,
    specific_errors: Optional[Union[Type[Exception], tuple]] = None,
) -> Callable[[T], T]:
    """
    统一错误处理装饰器
    """
    def decorator(func: T) -> T:
        is_async = inspect.iscoroutinefunction(func) or (
            hasattr(func, "__wrapped__") and inspect.iscoroutinefunction(func.__wrapped__)
        )

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if specific_errors and not isinstance(e, specific_errors):
                        raise

                    if log_error:
                        from core.context import trace_id_var
                        cid = trace_id_var.get("-")
                        func_logger = logging.getLogger(func.__module__ or __name__)
                        message = error_message or f"{func.__name__} 执行失败"
                        func_logger.error(f"[{cid}] {message}: {str(e)}", exc_info=True)

                    if reraise:
                        raise

                    return default_return
            return cast(T, async_wrapper)
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if specific_errors and not isinstance(e, specific_errors):
                        raise

                    if log_error:
                        from core.context import trace_id_var
                        cid = trace_id_var.get("-")
                        func_logger = logging.getLogger(func.__module__ or __name__)
                        message = error_message or f"{func.__name__} 执行失败"
                        func_logger.error(f"[{cid}] {message}: {str(e)}", exc_info=True)

                    if reraise:
                        raise

                    return default_return
            return cast(T, sync_wrapper)

    return decorator

def handle_telegram_errors(default_return: Any = None, max_retries: int = 3) -> Callable[[T], T]:
    """
    专门处理Telegram API错误的装饰器
    自动处理FloodWaitError等常见错误
    """
    def decorator(func: T) -> T:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
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
        return cast(T, wrapper)
    return decorator

def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], tuple] = Exception,
) -> Callable[[T], T]:
    """
    失败自动重试装饰器
    """
    def decorator(func: T) -> T:
        is_async = inspect.iscoroutinefunction(func) or (
            hasattr(func, "__wrapped__") and inspect.iscoroutinefunction(func.__wrapped__)
        )
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
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
            return cast(T, async_wrapper)
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
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
            return cast(T, sync_wrapper)

    return decorator

def log_execution(
    include_args: bool = False,
    include_result: bool = False,
    level: int = logging.DEBUG,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    记录函数执行详情的装饰器
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        is_async = inspect.iscoroutinefunction(func) or (
            hasattr(func, "__wrapped__") and inspect.iscoroutinefunction(func.__wrapped__)
        )

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                from core.context import trace_id_var
                cid = trace_id_var.get("-")
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
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                from core.context import trace_id_var
                cid = trace_id_var.get("-")
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
            return sync_wrapper

    return decorator
