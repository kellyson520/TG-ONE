from __future__ import annotations
import logging
from pathlib import Path
from contextlib import asynccontextmanager, contextmanager
from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.engine import Engine
from core.config import settings

logger = logging.getLogger(__name__)

from typing import Any, Dict, Optional, Generator, AsyncGenerator
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncEngine

# Singletons
_engine: Optional[Engine] = None
_session_factory: Optional[scoped_session[Session]] = None
_async_write_engine: Optional[AsyncEngine] = None
_async_read_engine: Optional[AsyncEngine] = None
_write_factory: Optional[async_sessionmaker[AsyncSession]] = None
_read_factory: Optional[async_sessionmaker[AsyncSession]] = None

# 导出清理函数
async def dispose_all_engines() -> None:
    """异步关闭所有数据库引擎"""
    global _engine
    # 1. 处理同步引擎
    if _engine:
        try:
            _engine.dispose()
            _engine = None
            logger.info("[DbFactory] 同步数据库引擎已释放")
        except Exception as e:
            logger.error(f"[DbFactory] 释放同步引擎失败: {e}")
            
    # 2. 处理异步读写引擎
    # 优先处理类变量中的引擎
    engines_to_dispose = []
    if hasattr(DbFactory, "_async_write_engine") and DbFactory._async_write_engine:
        engines_to_dispose.append(("Async Write", DbFactory._async_write_engine))
        DbFactory._async_write_engine = None
        
    if hasattr(DbFactory, "_async_read_engine") and DbFactory._async_read_engine:
        engines_to_dispose.append(("Async Read", DbFactory._async_read_engine))
        DbFactory._async_read_engine = None

    # 处理全局变量中的引擎 (如果有)
    global _async_write_engine, _async_read_engine
    if _async_write_engine:
        engines_to_dispose.append(("Global Async Write", _async_write_engine))
        _async_write_engine = None
    if _async_read_engine:
        engines_to_dispose.append(("Global Async Read", _async_read_engine))
        _async_read_engine = None

    for name, engine in engines_to_dispose:
        try:
            await engine.dispose()
            logger.info(f"[DbFactory] {name} 数据库引擎已释放")
        except Exception as e:
            logger.error(f"[DbFactory] 释放 {name} 引擎失败: {e}")



class DbFactory:
    """Database Factory for creating Engines and Sessions"""
    _async_read_engine: Optional[AsyncEngine] = None
    _async_write_engine: Optional[AsyncEngine] = None
    _read_factory: Optional[async_sessionmaker[AsyncSession]] = None
    _write_factory: Optional[async_sessionmaker[AsyncSession]] = None

    @staticmethod
    def _get_db_url() -> str:
        """Helper to resolve DB URL and ensure directories exist"""
        db_path_str = settings.DB_PATH
        if not db_path_str.endswith('.db'):
            target_dir = Path(db_path_str)
            target_dir.mkdir(parents=True, exist_ok=True)
            db_path_full = target_dir / "forwarder.db"
        else:
            db_path_obj = Path(db_path_str)
            db_path_obj.parent.mkdir(parents=True, exist_ok=True)
            db_path_full = db_path_obj
        return f"sqlite+aiosqlite:///{db_path_full.as_posix()}"

    @classmethod
    def get_engine(cls) -> Engine:
        global _engine
        if _engine is None:
            db_url = cls._get_db_url()
            sync_url = db_url.replace("sqlite+aiosqlite", "sqlite")

            _engine = create_engine(
                sync_url,
                poolclass=QueuePool,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                pool_recycle=settings.DB_POOL_RECYCLE,
                connect_args={"check_same_thread": False, "timeout": 30}
            )

            with _engine.connect() as conn:
                from core.helpers.sqlite_config import setup_sqlite_performance
                setup_sqlite_performance(_engine)
                conn.execute(text("SELECT 1"))
                conn.commit()
        return _engine

    @classmethod
    def get_async_engine(cls, readonly: bool = False) -> AsyncEngine:
        db_url = cls._get_db_url()

        if readonly:
            if not hasattr(cls, '_async_read_engine') or cls._async_read_engine is None:
                cls._async_read_engine = create_async_engine(
                    db_url,
                    pool_size=settings.DB_POOL_SIZE,
                    max_overflow=settings.DB_MAX_OVERFLOW,
                    pool_timeout=settings.DB_POOL_TIMEOUT,
                    pool_recycle=settings.DB_POOL_RECYCLE,
                    connect_args={"check_same_thread": False, "timeout": 30}
                )
                from core.helpers.sqlite_config import setup_sqlite_performance
                # 只处理读引擎，不启用 BEGIN IMMEDIATE 以优化性能 (只读连接不需要 BEGIN IMMEDIATE)
                setup_sqlite_performance(cls._async_read_engine, enable_immediate=False)
            return cls._async_read_engine
        else:
            if not hasattr(cls, '_async_write_engine') or cls._async_write_engine is None:
                cls._async_write_engine = create_async_engine(
                    db_url,
                    pool_size=settings.DB_POOL_SIZE,  # 使用配置的连接池大小
                    max_overflow=settings.DB_MAX_OVERFLOW,  # 使用配置的溢出连接数
                    pool_timeout=settings.DB_POOL_TIMEOUT,
                    pool_recycle=settings.DB_POOL_RECYCLE,
                    connect_args={"check_same_thread": False, "timeout": 60}
                )
                from core.helpers.sqlite_config import setup_sqlite_performance
                setup_sqlite_performance(cls._async_write_engine)
            return cls._async_write_engine

    @classmethod
    def get_session_factory(cls) -> scoped_session[Session]:
        global _session_factory
        if _session_factory is None:
            engine = cls.get_engine()
            _session_factory = scoped_session(sessionmaker(bind=engine))
        return _session_factory

    @classmethod
    def get_async_session_factory(cls, readonly: bool = False) -> async_sessionmaker[AsyncSession]:
        if readonly:
            if not hasattr(cls, '_read_factory') or cls._read_factory is None:
                engine = cls.get_async_engine(readonly=True)
                cls._read_factory = async_sessionmaker(
                    engine, expire_on_commit=False, class_=AsyncSession
                )
            return cls._read_factory
        else:
            if not hasattr(cls, '_write_factory') or cls._write_factory is None:
                engine = cls.get_async_engine(readonly=False)
                cls._write_factory = async_sessionmaker(
                    engine, expire_on_commit=False, class_=AsyncSession
                )
            return cls._write_factory


# Legacy function aliases for compatibility (now expected to be imported from here)
def get_engine() -> Engine:
    return DbFactory.get_engine()


def get_async_engine(readonly: bool = False) -> AsyncEngine:
    return DbFactory.get_async_engine(readonly)


def get_session_factory() -> scoped_session[Session]:
    return DbFactory.get_session_factory()


def get_session() -> Session:
    return get_session_factory()()


def get_read_session() -> Session:
    return get_session()


def get_dedup_session() -> Session:
    return get_session()


def get_async_session_factory(readonly: bool = False) -> async_sessionmaker[AsyncSession]:
    return DbFactory.get_async_session_factory(readonly)


def get_async_session(readonly: bool = False) -> AsyncSession:
    return get_async_session_factory(readonly)()


@asynccontextmanager
async def AsyncSessionManager(readonly: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """Async session manager context manager"""
    factory = get_async_session_factory(readonly=readonly)
    async with factory() as session:
        try:
            yield session
            if session.in_transaction() and not readonly:
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
        finally:
            await session.close()


@contextmanager
def SessionManager(readonly: bool = False) -> Generator[Session, None, None]:
    """Synchronous session manager context manager for legacy support"""
    session = get_session()
    try:
        yield session
        if not readonly:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def async_get_db_health() -> Dict[str, Any]:
    """Get database health status (asynchronous)"""
    try:
        async_engine = DbFactory.get_async_engine()
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"connected": True, "status": "healthy"}
    except Exception as e:
        return {"connected": False, "status": "error", "error": str(e)}


def get_db_health() -> Dict[str, Any]:
    """Get database health status (synchronous)"""
    try:
        engine = DbFactory.get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"connected": True, "status": "healthy"}
    except Exception as e:
        return {"connected": False, "status": "error", "error": str(e)}


def analyze_database() -> bool:
    """Run ANALYZE on the database"""
    try:
        engine = DbFactory.get_engine()
        with engine.connect() as conn:
            conn.execute(text("ANALYZE"))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"ANALYZE failed: {e}")
        return False


async def async_analyze_database() -> bool:
    """Run ANALYZE on the database (async)"""
    try:
        engine = DbFactory.get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(text("ANALYZE"))
        return True
    except Exception as e:
        logger.error(f"Async ANALYZE failed: {e}")
        return False


def vacuum_database() -> bool:
    """Run VACUUM on the database"""
    try:
        engine = DbFactory.get_engine()
        # VACUUM cannot be run inside a transaction
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("VACUUM"))
        return True
    except Exception as e:
        logger.error(f"VACUUM failed: {e}")
        return False


async def async_vacuum_database() -> bool:
    """Run VACUUM on the database (async)"""
    try:
        engine = DbFactory.get_async_engine()
        async with engine.connect() as conn:
            # For async, we try executing it directly.
            # Note: some drivers/configurations might still struggle with VACUUM.
            await conn.execute(text("VACUUM"))
        return True
    except Exception as e:
        logger.error(f"Async VACUUM failed: {e}")
        return False


async def async_cleanup_old_logs(days: int) -> int:
    """清理旧日志 (异步)"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import delete
        from models.models import RuleLog, ErrorLog, AuditLog
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted_count = 0
        
        async with AsyncSessionManager() as session:
            # 1. 清理转发日志
            stmt1 = delete(RuleLog).where(RuleLog.created_at < cutoff)
            res1 = await session.execute(stmt1)
            deleted_count += res1.rowcount
            
            # 2. 清理错误日志
            stmt2 = delete(ErrorLog).where(ErrorLog.created_at < cutoff)
            res2 = await session.execute(stmt2)
            deleted_count += res2.rowcount
            
            # 3. 清理审计日志
            stmt3 = delete(AuditLog).where(AuditLog.created_at < cutoff)
            res3 = await session.execute(stmt3)
            deleted_count += res3.rowcount

            # 4. 清理已完成/失败的任务队列
            from models.models import TaskQueue
            from sqlalchemy import select, func
            
            # [Stats] 在删除前统计数量，用于持久化归档
            count_stmt = select(func.count()).where(
                TaskQueue.status.in_(['completed', 'failed']),
                TaskQueue.updated_at < cutoff
            )
            tasks_to_remove = (await session.execute(count_stmt)).scalar() or 0
            
            stmt4 = delete(TaskQueue).where(
                TaskQueue.status.in_(['completed', 'failed']),
                TaskQueue.updated_at < cutoff
            )
            res4 = await session.execute(stmt4)
            deleted_count += res4.rowcount
            
            # [Stats] 持久化统计数据
            if tasks_to_remove > 0 or (res1.rowcount + res2.rowcount + res3.rowcount) > 0:
                try:
                    from core.stats_manager import stats_manager
                    logs_removed = res1.rowcount + res2.rowcount + res3.rowcount
                    await stats_manager.async_record_cleanup(
                        tasks_removed=tasks_to_remove,
                        logs_removed=logs_removed
                    )
                except ImportError:
                    pass
                except Exception as stats_err:
                    logger.warning(f"Failed to persist cleanup stats: {stats_err}")
            
            await session.commit()
            logger.info(f"已清理 {days} 天前的旧日志，共删除 {deleted_count} 条记录")
            return deleted_count
    except Exception as e:
        logger.error(f"清理旧日志失败: {e}")
        return 0


def cleanup_old_logs(days: int) -> int:
    """清理旧日志 (同步)"""
    try:
        import asyncio
        # 创建新的事件循环运行异步函数
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # 如果已经在运行，则无法直接 run_until_complete，这种情况在 controller 中可能发生
            # 但通常同步调用是在独立的脚本或线程中
            return 0
            
        return loop.run_until_complete(async_cleanup_old_logs(days))
    except Exception as e:
        logger.error(f"同步清理旧日志失败: {e}")
        return 0


async def async_get_database_info() -> Optional[Dict[str, Any]]:
    """Get database file info"""
    try:
        db_path = Path(settings.DB_PATH)
        if not db_path.suffix == '.db':
            db_path = db_path / "forwarder.db"

        db_size = db_path.stat().st_size if db_path.exists() else 0
        wal_path = db_path.with_suffix('.db-wal')
        wal_size = wal_path.stat().st_size if wal_path.exists() else 0

        return {
            "db_size": db_size,
            "wal_size": wal_size,
            "total_size": db_size + wal_size,
            "table_count": 0,  # Could be improved
            "index_count": 0
        }
    except Exception:
        return None


# 已移除同步 PRAGMA 事件监听，转由 sqlite_config 统一管理
