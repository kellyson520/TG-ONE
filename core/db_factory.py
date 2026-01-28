from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from core.config import settings

logger = logging.getLogger(__name__)

# Singletons
_engine = None
_session_factory = None

class DbFactory:
    """Database Factory for creating Engines and Sessions"""
    
    @staticmethod
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

    @classmethod
    def get_engine(cls):
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
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
                conn.execute(text("PRAGMA cache_size=-64000")) 
                conn.execute(text("PRAGMA mmap_size=268435456")) 
                conn.commit()
        return _engine

    @classmethod
    def get_async_engine(cls, readonly: bool = False):
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
            return cls._async_read_engine
        else:
            if not hasattr(cls, '_async_write_engine') or cls._async_write_engine is None:
                cls._async_write_engine = create_async_engine(
                    db_url,
                    pool_size=1, # Single writer
                    max_overflow=0,
                    pool_timeout=60,
                    pool_recycle=settings.DB_POOL_RECYCLE,
                    connect_args={"check_same_thread": False, "timeout": 60} 
                )
            return cls._async_write_engine

    @classmethod
    def get_session_factory(cls):
        global _session_factory
        if _session_factory is None:
            engine = cls.get_engine()
            _session_factory = scoped_session(sessionmaker(bind=engine))
        return _session_factory

    @classmethod
    def get_async_session_factory(cls, readonly: bool = False):
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
def get_engine():
    return DbFactory.get_engine()

def get_async_engine(readonly: bool = False):
    return DbFactory.get_async_engine(readonly)

def get_session_factory():
    return DbFactory.get_session_factory()

def get_session():
    return get_session_factory()()

def get_async_session_factory(readonly: bool = False):
    return DbFactory.get_async_session_factory(readonly)

@asynccontextmanager
async def AsyncSessionManager(readonly: bool = False):
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

from sqlalchemy.engine import Engine
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA mmap_size=268435456") 
        cursor.close()
    except Exception as e:
        logger.warning(f"Failed to set PRAGMA for async connection: {e}")
