from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional, Any
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_url: Optional[str] = None, engine: Optional[AsyncEngine] = None) -> None:
        logger.info(f"[Database] 初始化数据库连接，模式={'共享引擎' if engine else '新建引擎'}")
        
        if engine:
            # 模式 A: 使用传入的现有引擎 (Unified Mode)
            self.engine = engine
            logger.info(f"[Database] 使用共享引擎: {engine.url}")
        elif db_url:
            # 自动修正 SQLite URL 以使用 aiosqlite 驱动
            if db_url.startswith('sqlite://') and 'aiosqlite' not in db_url:
                db_url = db_url.replace('sqlite://', 'sqlite+aiosqlite://')
                logger.info(f"[Database] 修正SQLite URL: {db_url}")

            # 模式 B: 创建新引擎 (Legacy/Standalone Mode)
            # 启用 WAL 模式，这对 SQLite 并发至关重要
            self.engine = create_async_engine(
                db_url, 
                echo=False,
                connect_args={
                    "check_same_thread": False, 
                    "timeout": 30  # 增加等待超时，避免数据库锁死
                },
                pool_size=20,  # 增大连接池
                max_overflow=10  # 允许溢出连接
            )
            logger.info(f"[Database] 创建新引擎: {db_url}")
        else:
            raise ValueError("Must provide either db_url or engine")
        
        self.session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )
        logger.info(f"[Database] 会话工厂已初始化")

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        session = None
        try:
            session = self.session_factory()
            logger.debug(f"[Database] 会话创建成功: {id(session)}")
            
            yield session
            
            if session.in_transaction():
                await session.commit()
                logger.debug(f"[Database] 事务提交成功: {id(session)}")
        except Exception as e:
            if session and session.in_transaction():
                await session.rollback()
                logger.error(f"[Database] 事务回滚: {id(session)}，错误={e}")
            logger.error(f"[Database] 会话处理失败: {id(session)}，错误={e}", exc_info=True)
            raise
        finally:
            if session:
                await session.close()
                logger.debug(f"[Database] 会话关闭成功: {id(session)}")

    async def close(self) -> None:
        logger.info(f"[Database] 关闭数据库引擎")
        await self.engine.dispose()
        logger.info(f"[Database] 数据库引擎已关闭")

