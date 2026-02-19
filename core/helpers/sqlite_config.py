import logging
from sqlalchemy import event, text

logger = logging.getLogger(__name__)

def setup_sqlite_performance(engine, enable_immediate: bool = True):
    """
    为 SQLite 引擎配置高性能 PRAGMA 参数并选择性启用 BEGIN IMMEDIATE 事务模式。
    支持 AsyncEngine 和 Sync Engine。
    """
    target_engine = engine.sync_engine if hasattr(engine, 'sync_engine') else engine
    
    # 1. 基础连接参数设置
    @event.listens_for(target_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB
            cursor.execute("PRAGMA busy_timeout=30000")  # 30s
            cursor.execute("PRAGMA journal_size_limit=20000000")  # 20MB
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA mmap_size=0")
        except Exception as e:
            logger.error(f"[SQLiteConfig] 设置 PRAGMA 失败: {e}")
        finally:
            cursor.close()

    # 2. 强制 BEGIN IMMEDIATE 以解决锁升级导致的 database is locked
    if enable_immediate:
        @event.listens_for(target_engine, "begin")
        def do_begin_immediate(conn):
            # logger.debug(f"[SQLiteConfig] Starting transaction with BEGIN IMMEDIATE on {conn}")
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        logger.info(f"[SQLiteConfig] 已为引擎 {engine.url} 配置高性能 WAL & BEGIN IMMEDIATE 策略")
    else:
        logger.info(f"[SQLiteConfig] 已为引擎 {engine.url} 配置高性能 WAL 策略 (未启用 BEGIN IMMEDIATE)")


def apply_pragma_to_connection(dbapi_connection):
    """手动将 PRAGMA 应用于现有连接（用于特定的低级操作）"""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
    finally:
        cursor.close()
