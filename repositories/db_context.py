"""
[Refactor] 统一数据库会话管理器
现在直接代理到 Core Container，确保全局使用同一个 Engine 和连接池。
"""
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def async_db_session():
    """
    异步数据库会话上下文管理器
    统一使用 container.db.get_session()
    """
    # [CRITICAL] 延迟导入以避免循环依赖
    from core.container import container
    
    async with container.db.get_session() as session:
        try:
            yield session
            # container.db.get_session 默认 auto-commit 吗？
            # 通常 SQLAlchemy 的 session maker 配置了 expire_on_commit=False
            # 这里我们显式 commit 以确保逻辑闭环
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"DB Session Error: {e}")
            raise
        finally:
            await session.close()


# 兼容旧代码的同步别名（如果有的话，建议尽快废弃）
def db_session():
    raise NotImplementedError("同步 db_session 已废弃，请使用 async_db_session")


# 兼容旧代码的装饰器
def safe_db_operation(func):
    """
    [Deprecated] 旧版数据库操作装饰器
    现在直接使用 async_db_session() 上下文管理器即可
    """
    logger.warning(f"safe_db_operation decorator is deprecated for function: {func.__name__}")
    return func


async def async_safe_db_operation(operation, default_return=None):
    """
    [Compatibility] 兼容旧版 async_safe_db_operation
    接受一个接受 session 的异步函数并执行它
    """
    try:
        async with async_db_session() as session:
            return await operation(session)
    except Exception as e:
        logger.error(f"Async DB Operation Failed: {e}")
        return default_return
