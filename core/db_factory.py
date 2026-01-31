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
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
                conn.execute(text("PRAGMA cache_size=-64000"))
                conn.execute(text("PRAGMA mmap_size=268435456"))
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
            return cls._async_read_engine
        else:
            if not hasattr(cls, '_async_write_engine') or cls._async_write_engine is None:
                cls._async_write_engine = create_async_engine(
                    db_url,
                    pool_size=1,  # Single writer
                    max_overflow=0,
                    pool_timeout=60,
                    pool_recycle=settings.DB_POOL_RECYCLE,
                    connect_args={"check_same_thread": False, "timeout": 60}
                )
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
    """Cleanup old logs (dummy for now, but referenced by manage_db.py)"""
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


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.close()
    except Exception as e:
        logger.warning(f"Failed to set PRAGMA for async connection: {e}")
