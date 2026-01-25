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

def get_engine():
    global _engine
    if _engine is None:
        db_path = Path(settings.DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        db_url = f"sqlite+aiosqlite:///{settings.DB_PATH}"
        if not settings.DB_PATH.endswith('.db'):
            db_url = f"sqlite+aiosqlite:///{settings.DB_PATH}/forwarder.db"

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
            conn.commit()

    return _engine

def get_async_engine():
    global _async_engine
    if _async_engine is None:
        db_url = f"sqlite+aiosqlite:///{settings.DB_PATH}"
        if not settings.DB_PATH.endswith('.db'):
            db_url = f"sqlite+aiosqlite:///{settings.DB_PATH}/forwarder.db"
            
        _async_engine = create_async_engine(
            db_url,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            connect_args={"check_same_thread": False, "timeout": 30}
        )
    return _async_engine

def get_session_factory():
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = scoped_session(sessionmaker(bind=engine))
    return _session_factory

def get_session():
    """获取同步会话 (Compatibility)"""
    return get_session_factory()()

def get_async_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
    return _async_session_factory

@asynccontextmanager
async def AsyncSessionManager():
    """异步会话上下文管理器 (Compatibility)"""
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
        finally:
            await session.close()
