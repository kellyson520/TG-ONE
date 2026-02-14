from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
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
            from core.config import settings
            
            connect_args = {"timeout": 30}
            if 'sqlite' in db_url:
                connect_args["check_same_thread"] = False
                
            self.engine = create_async_engine(
                db_url, 
                echo=False,
                connect_args=connect_args,
                pool_size=settings.DB_POOL_SIZE,  # 使用配置的连接池大小
                max_overflow=settings.DB_MAX_OVERFLOW  # 使用配置的溢出连接数
            )

            # 关键修复: 显式启用 WAL 模式
            if 'sqlite' in db_url:
                from sqlalchemy import event
                import os
                
                # 尝试解析并记录绝对路径
                try:
                    # 简单去除协议头
                    db_path = db_url.replace('sqlite+aiosqlite:///', '').replace('sqlite:///', '')
                    # 处理相对路径
                    if not os.path.isabs(db_path):
                        db_path = os.path.abspath(db_path)
                    logger.info(f"[Database] SQLite数据库文件路径: {db_path}")
                    
                    # 检查目录是否存在，不存在则提醒（虽然SQLAlchemy通常会创建文件，但目录必须存在）
                    db_dir = os.path.dirname(db_path)
                    if db_dir and not os.path.exists(db_dir):
                         logger.warning(f"[Database] 警告: 数据库目录不存在: {db_dir}")
                except Exception as e:
                    logger.warning(f"[Database] 无法解析数据库路径: {e}")

                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    try:
                        cursor.execute("PRAGMA journal_mode=WAL")
                        cursor.execute("PRAGMA synchronous=NORMAL")
                        # 增加缓存以减少磁盘I/O
                        cursor.execute("PRAGMA cache_size=-64000") # 64MB
                        cursor.execute("PRAGMA busy_timeout=5000") # 5秒等待
                        
                        # 验证
                        cursor.execute("PRAGMA journal_mode")
                        mode = cursor.fetchone()[0]
                        if mode.upper() != 'WAL':
                            logger.warning(f"[Database] ⚠️ 警告: 无法启用 WAL 模式! 当前模式: {mode}")
                        else:
                            # 仅在第一次连接时记录，避免刷屏
                            # logger.info(f"[Database] ✅ WAL 模式已启用")
                            pass
                            
                    except Exception as e:
                        logger.error(f"[Database] 设置 SQLite PRAGMA 失败: {e}")
                    finally:
                        cursor.close()

                # 监听连接事件，确保每次连接都启用 WAL
                # 对于 AsyncEngine，我们需要监听 sync_engine
                event.listen(self.engine.sync_engine, "connect", set_sqlite_pragma)

            logger.info(f"[Database] 创建新引擎: {db_url} (已配置 WAL & 性能参数)")
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
            
            # Note: We only commit if we are actually in a transaction
            # and not in a nested session (though session_factory creates fresh sessions).
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

    @asynccontextmanager
    async def get_session(self, existing_session: Optional[AsyncSession] = None) -> AsyncIterator[AsyncSession]:
        """
        获取一个会话。如果提供了现有会话且处于活动状态，则重用它；
        否则创建一个新的会话上下文。
        """
        if existing_session and existing_session.is_active:
            yield existing_session
        else:
            async with self.session() as session:
                yield session

    async def close(self) -> None:
        logger.info(f"[Database] 关闭数据库引擎")
        await self.engine.dispose()
        logger.info(f"[Database] 数据库引擎已关闭")

