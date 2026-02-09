import asyncio
import logging
import random
import functools
from typing import Callable, Any, TypeVar, Coroutine
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

T = TypeVar("T")

def retry_on_db_lock(
    retries: int = 5,
    initial_delay: float = 0.5,
    max_delay: float = 5.0,
    backoff_factor: float = 2.0
):
    """
    Decorator to retry async database operations when SQLite is locked.
    
    Usage:
        @retry_on_db_lock(retries=3)
        async def save_data(data):
            async with db.get_session() as session:
                ...
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except OperationalError as e:
                    last_exception = e
                    # Check if it's a "database is locked" error
                    if "locked" in str(e).lower() or "busy" in str(e).lower():
                        if attempt < retries - 1:
                            # Exponential backoff with jitter
                            sleep_time = delay + (random.random() * delay * 0.1)
                            logger.warning(
                                f"📦 [DB-LOCK] Database is locked (Attempt {attempt+1}/{retries}). "
                                f"Retrying in {sleep_time:.2f}s... (Error: {e})"
                            )
                            await asyncio.sleep(sleep_time)
                            delay = min(delay * backoff_factor, max_delay)
                            continue
                    
                    # If not a lock error, or out of retries, re-raise
                    raise
                except Exception:
                    # Non-DB errors should not be retried here
                    raise
            
            logger.error(f"❌ [DB-LOCK] Failed after {retries} retries due to database locking.")
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator
