from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_url: Optional[str] = None, engine: Optional[AsyncEngine] = None) -> None:
        logger.info(f"[Database] 初始化数据库连接，模式={'共享引擎' if engine else '新建引擎'}")
        
        self.read_engine = None
        if engine:
            # 模式 A: 使用传入的现有引擎 (Unified Mode)
            self.engine = engine
            logger.info(f"[Database] 使用共享引擎: {engine.url}")
            
            # [Optimization] 尝试从工厂获取只读引擎，以支持非锁定读取
            try:
                from core.db_factory import DbFactory
                self.read_engine = DbFactory.get_async_engine(readonly=True)
            except Exception:
                self.read_engine = self.engine
        elif db_url:
            # 自动修正 SQLite URL 以使用 aiosqlite 驱动
            if db_url.startswith('sqlite://') and 'aiosqlite' not in db_url:
                db_url = db_url.replace('sqlite://', 'sqlite+aiosqlite://')
                logger.info(f"[Database] 修正SQLite URL: {db_url}")

            # 模式 B: 创建新引擎 (Legacy/Standalone Mode)
            from core.config import settings
            
            connect_args = {"timeout": 30}
            if 'sqlite' in db_url:
                connect_args["check_same_thread"] = False
                
            self.engine = create_async_engine(
                db_url, 
                echo=False,
                connect_args=connect_args,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW
            )

            # 关键修复: 显式启用 WAL 模式与 BEGIN IMMEDIATE
            if 'sqlite' in db_url:
                from core.helpers.sqlite_config import setup_sqlite_performance
                setup_sqlite_performance(self.engine)
                
                # 创建对应的读引擎
                self.read_engine = create_async_engine(
                    db_url,
                    connect_args=connect_args,
                    pool_size=settings.DB_POOL_SIZE,
                    max_overflow=settings.DB_MAX_OVERFLOW
                )
                setup_sqlite_performance(self.read_engine, enable_immediate=False)

            logger.info(f"[Database] 创建新引擎: {db_url} (已配置 WAL & BEGIN IMMEDIATE & 性能参数)")
        else:
            raise ValueError("Must provide either db_url or engine")
        
        self._write_factory = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )
        self._read_factory = async_sessionmaker(
            self.read_engine or self.engine, expire_on_commit=False, class_=AsyncSession
        )
        logger.info(f"[Database] 读写会话工厂已初始化")

    @asynccontextmanager
    async def session(self, readonly: bool = False) -> AsyncIterator[AsyncSession]:
        """获取数据库会话，支持只读模式"""
        session = None
        try:
            factory = self._read_factory if readonly else self._write_factory
            session = factory()
            logger.debug(f"[Database] 会话创建成功 ({'READ' if readonly else 'WRITE'}): {id(session)}")
            
            yield session
            
            if not readonly and session.in_transaction():
                await session.commit()
                logger.debug(f"[Database] 事务提交成功: {id(session)}")
        except Exception as e:
            if session and session.in_transaction():
                await session.rollback()
                logger.error(f"[Database] 事务回滚: {id(session)}，错误={e}")
            logger.error(f"[Database] 会话处理失败: {id(session)}，错误={e}")
            raise
        finally:
            if session:
                await session.close()
                logger.debug(f"[Database] 会话关闭成功: {id(session)}")

    @asynccontextmanager
    async def get_session(self, existing_session: Optional[AsyncSession] = None, readonly: bool = False) -> AsyncIterator[AsyncSession]:
        """
        获取一个会话。如果提供了现有会话且处于活动状态，则重用它；
        否则创建一个新的会话上下文。
        """
        if existing_session and existing_session.is_active:
            yield existing_session
        else:
            async with self.session(readonly=readonly) as session:
                yield session

    async def close(self) -> None:
        logger.info(f"[Database] 关闭数据库引擎")
        await self.engine.dispose()
        if self.read_engine and self.read_engine is not self.engine:
            await self.read_engine.dispose()
        logger.info(f"[Database] 数据库引擎已关闭")

