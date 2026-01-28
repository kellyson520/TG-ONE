"""
Modular Models Proxy
This file maintains backward compatibility while redirecting to split model files.
"""
from models.base import Base
from models.chat import Chat
from models.rule import (
    ForwardRule, ForwardMapping, Keyword, ReplaceRule, 
    MediaTypes, MediaExtensions, RuleSync, PushConfig, 
    RSSConfig, RSSPattern
)
from models.user import User, AuditLog, ActiveSession, AccessControlList
from models.stats import ChatStatistics, RuleStatistics, RuleLog
from models.system import SystemConfiguration, ErrorLog, TaskQueue, RSSSubscription
from models.dedup import MediaSignature
from models.migration import migrate_db

# Database factory function wrappers (using lazy imports to avoid architecture violation)
# These functions are provided for backward compatibility only.
# New code should import directly from core.db_factory

def get_engine():
    """Get database engine (lazy import wrapper)"""
    from core.db_factory import get_engine as _get_engine
    return _get_engine()

def get_session_factory():
    """Get session factory (lazy import wrapper)"""
    from core.db_factory import get_session_factory as _get_session_factory
    return _get_session_factory()

def get_async_engine():
    """Get async database engine (lazy import wrapper)"""
    from core.db_factory import get_async_engine as _get_async_engine
    return _get_async_engine()

def get_session():
    """Get a database session (lazy import wrapper)"""
    from core.db_factory import get_session as _get_session
    return _get_session()

def get_read_session():
    """Get a read-only database session (lazy import wrapper)"""
    from core.db_factory import get_read_session
    return get_read_session()

def get_dedup_session():
    """Get a dedup database session (lazy import wrapper)"""
    from core.db_factory import get_dedup_session
    return get_dedup_session()

# Async session manager (lazy import wrapper)
def AsyncSessionManager(readonly: bool = False):
    """Get async session manager (lazy import wrapper)"""
    from core.db_factory import AsyncSessionManager as _AsyncSessionManager
    return _AsyncSessionManager(readonly=readonly)

def SessionManager(readonly: bool = False):
    """Get synchronous session manager (lazy import wrapper)"""
    from core.db_factory import SessionManager as _SessionManager
    return _SessionManager(readonly=readonly)

def get_async_session(readonly: bool = False):
    """Get async session (lazy import wrapper)"""
    from core.db_factory import get_async_session
    return get_async_session(readonly=readonly)

# Database health check functions
def analyze_database():
    """Run ANALYZE on the database (lazy wrapper)"""
    from core.db_factory import analyze_database
    return analyze_database()

async def async_analyze_database():
    """Run ANALYZE on the database (async lazy wrapper)"""
    from core.db_factory import async_analyze_database
    return await async_analyze_database()

def vacuum_database():
    """Run VACUUM on the database (lazy wrapper)"""
    from core.db_factory import vacuum_database
    return vacuum_database()

async def async_vacuum_database():
    """Run VACUUM on the database (async lazy wrapper)"""
    from core.db_factory import async_vacuum_database
    return await async_vacuum_database()

async def async_cleanup_old_logs(days: int):
    """Cleanup old logs (async lazy wrapper)"""
    from core.db_factory import async_cleanup_old_logs
    return await async_cleanup_old_logs(days)

async def async_get_database_info():
    """Get database info (async lazy wrapper)"""
    from core.db_factory import async_get_database_info
    return await async_get_database_info()

def backup_database(db_path=None, backup_dir=None):
    """Backup database (lazy wrapper)"""
    from repositories.backup import backup_database
    return backup_database(db_path, backup_dir)

def get_db_health():
    """Get database health status (lazy wrapper)"""
    from core.db_factory import get_db_health
    return get_db_health()

async def async_get_db_health():
    """Get database health status (async lazy wrapper)"""
    from core.db_factory import async_get_db_health
    return await async_get_db_health()

# Re-export all for backward compatibility
__all__ = [
    'Base',
    'Chat',
    'ForwardRule', 'ForwardMapping', 'Keyword', 'ReplaceRule', 
    'MediaTypes', 'MediaExtensions', 'RuleSync', 'PushConfig', 
    'RSSConfig', 'RSSPattern',
    'User', 'AuditLog', 'ActiveSession', 'AccessControlList',
    'ChatStatistics', 'RuleStatistics', 'RuleLog',
    'SystemConfiguration', 'ErrorLog', 'TaskQueue', 'RSSSubscription',
    'MediaSignature', 'migrate_db',
    # Database factory functions (lazy wrappers)
    'get_engine', 'get_session_factory', 'get_async_engine',
    'get_session', 'get_read_session', 'get_dedup_session',
    'AsyncSessionManager', 'SessionManager', 'get_async_session',
    # Database health check and maintenance functions
    'get_db_health', 'async_get_db_health',
    'analyze_database', 'async_analyze_database',
    'vacuum_database', 'async_vacuum_database',
    'async_cleanup_old_logs', 'async_get_database_info',
    'backup_database'
]
