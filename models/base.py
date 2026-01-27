from sqlalchemy import create_engine, inspect, text, event
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# 全局引擎和会话工厂（单例模式）
_engine = None
_async_engine = None
_session_factory = None
_async_session_factory = None

def _get_db_url():
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

def get_engine():
    global _engine
    if _engine is None:
        db_url = _get_db_url()
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
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA cache_size=-64000")) 
            conn.execute(text("PRAGMA mmap_size=268435456")) 
            conn.commit()

    return _engine

from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Ensure WAL mode for all connections"""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA mmap_size=268435456") 
        cursor.close()
    except Exception as e:
        logger.warning(f"Failed to set PRAGMA for async connection: {e}")

def get_async_engine(readonly: bool = False):
    global _async_engine
    
    db_url = _get_db_url()
    
    if readonly:
        # 读库引擎: 较大的连接池
        if not hasattr(get_async_engine, '_async_read_engine') or get_async_engine._async_read_engine is None:
            get_async_engine._async_read_engine = create_async_engine(
                db_url,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                pool_recycle=settings.DB_POOL_RECYCLE,
                connect_args={"check_same_thread": False, "timeout": 30}
            )
        return get_async_engine._async_read_engine
    else:
        # 写库引擎: 限制并发 (SQLite 单写原则)，避免 busy locking
        # 虽然 WAL 支持并发读，但写只能一个。在应用层串行化写可以减少锁竞争。
        if not hasattr(get_async_engine, '_async_write_engine') or get_async_engine._async_write_engine is None:
            get_async_engine._async_write_engine = create_async_engine(
                db_url,
                pool_size=1, # 强制单写连接
                max_overflow=0, # 不允许溢出，排队等待
                pool_timeout=60, # 写锁等待时间稍长
                pool_recycle=settings.DB_POOL_RECYCLE,
                connect_args={"check_same_thread": False, "timeout": 60} 
            )
        return get_async_engine._async_write_engine

def get_session_factory():
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = scoped_session(sessionmaker(bind=engine))
    return _session_factory

def get_session():
    """获取同步会话 (Compatibility)"""
    return get_session_factory()()

def get_async_session_factory(readonly: bool = False):
    if readonly:
        if not hasattr(get_async_session_factory, '_read_factory') or get_async_session_factory._read_factory is None:
            engine = get_async_engine(readonly=True)
            get_async_session_factory._read_factory = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
        return get_async_session_factory._read_factory
    else:
        if not hasattr(get_async_session_factory, '_write_factory') or get_async_session_factory._write_factory is None:
            engine = get_async_engine(readonly=False)
            get_async_session_factory._write_factory = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
        return get_async_session_factory._write_factory

@asynccontextmanager
async def AsyncSessionManager(readonly: bool = False):
    """异步会话上下文管理器 (支持读写分离)"""
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
