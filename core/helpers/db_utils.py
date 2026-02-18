import asyncio
import logging
import functools
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

def async_db_retry(max_retries: int = 3, base_delay: float = 0.2):
    """
    异步数据库操作重试装饰器，专门用于处理 SQLite 'database is locked' 错误。
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except OperationalError as e:
                    last_error = e
                    error_msg = str(e).lower()
                    if "locked" in error_msg or "io error" in error_msg or "busy" in error_msg:
                        if attempt < max_retries - 1:
                            # 指数退避 + 随机抖动
                            delay = base_delay * (2 ** attempt)
                            logger.warning(
                                f"[DB_RETRY] 数据库锁定/IO错误，准备重试 ({attempt + 1}/{max_retries}). "
                                f"错误: {e}. 等待 {delay:.2f}s"
                            )
                            await asyncio.sleep(delay)
                            continue
                    raise # 如果不是锁定错误，或者超过重试次数，直接抛出
                except Exception:
                    raise # 其他异常不重试
            
            if last_error:
                logger.error(f"[DB_RETRY] 超过最大重试次数 ({max_retries})，操作失败: {last_error}")
                raise last_error
        return wrapper
    return decorator

# 为向后兼容提供别名
def retry_on_db_lock(retries: int = 5):
    return async_db_retry(max_retries=retries)
