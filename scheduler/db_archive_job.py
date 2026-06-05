from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any

from models.models import get_session, get_dedup_session, MediaSignature, ErrorLog, RuleLog, TaskQueue, ChatStatistics, RuleStatistics
from repositories.archive_store import write_parquet, compact_small_files
from core.helpers.metrics import ARCHIVE_RUN_TOTAL, ARCHIVE_RUN_SECONDS
from repositories.bloom_index import bloom
from models.models import analyze_database, vacuum_database
from pathlib import Path

logger = logging.getLogger(__name__)

# 确保归档系统初始化
def _ensure_archive_system():
    """确保归档系统已正确初始化"""
    try:
        from repositories.archive_init import init_archive_system
        if not init_archive_system():
            logger.warning("归档系统初始化失败，可能影响功能")
    except Exception as e:
        logger.error(f"归档系统初始化检查失败: {e}")
        logger.debug("归档系统初始化检查失败的详细信息", exc_info=True)

# 在模块加载时进行一次检查
_ensure_archive_system()

from repositories.archive_manager import get_archive_manager
from repositories.db_context import async_db_session

async def archive_once_async() -> None:
    """异步执行归档任务"""
    manager = get_archive_manager(async_db_session)
    await manager.run_archiving_cycle()

from core.config import settings

HOT_DAYS_SIGN = settings.HOT_DAYS_SIGN
HOT_DAYS_LOG = settings.HOT_DAYS_LOG
HOT_DAYS_STATS = settings.HOT_DAYS_STATS

def archive_once() -> None:
    """同步兼容接口，通过 ArchiveManager 执行归档周期。"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(archive_once_async())
        else:
            loop.run_until_complete(archive_once_async())
    except RuntimeError:
        asyncio.run(archive_once_async())

def archive_force() -> None:
    """强制归档：忽略保留天数阈值，全量归档当前所有热数据。"""
    logger.info("开始强制归档流程")
    
    async def _force_task():
        manager = get_archive_manager(async_db_session)
        # 临时将阈值设为 -1 以强制归档所有现有数据
        original_config = manager.archive_config.copy()
        try:
            for model in manager.archive_config:
                manager.archive_config[model] = -1 
            await manager.run_archiving_cycle()
        finally:
            manager.archive_config = original_config
            
        # 优化数据库
        try:
            from sqlalchemy import text
            from core.db_factory import get_engine
            analyze_database()
            with get_engine().connect() as conn:
                conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            vacuum_database()
        except Exception as e:
            logger.warning(f"强制归档后的数据库优化失败: {e}")

    import asyncio
    try:
        asyncio.run(_force_task())
    except Exception as e:
        logger.error(f"强制归档任务执行失败: {e}")

def garbage_collect_once() -> None:
    """执行一次垃圾清理：清理临时目录中过期文件。"""
    try:
        logger.debug("开始垃圾清理")
        keep_days = settings.GC_KEEP_DAYS
        cutoff = datetime.utcnow() - timedelta(days=max(0, keep_days))
        tmp_dirs = settings.GC_TEMP_DIRS
        if isinstance(tmp_dirs, str):
            tmp_dirs = [p.strip() for p in tmp_dirs.split(',') if p.strip()]
            
        removed = 0
        for d in tmp_dirs:
            p = Path(d)
            if not p.exists():
                logger.debug(f"临时目录不存在: {d}")
                continue
            logger.debug(f"清理临时目录: {d}")
            for item in p.rglob('*'):
                try:
                    if item.is_file():
                        # 使用 UTC 时间
                        mtime = datetime.fromtimestamp(item.stat().st_mtime, datetime.timezone.utc).replace(tzinfo=None)
                        if mtime < cutoff:
                            item.unlink(missing_ok=True)
                            removed += 1
                            logger.debug(f"删除过期文件: {item}")
                    elif item.is_dir():
                        # 尝试移除空目录
                        try:
                            next(item.iterdir())
                        except StopIteration:
                            item.rmdir()
                            logger.debug(f"删除空目录: {item}")
                except Exception as e:
                    logger.warning(f"清理文件/目录失败 {item}: {e}")
        logger.info(f"垃圾清理完成，删除文件约 {removed} 个")
    except Exception as e:
        logger.error(f"垃圾清理失败: {e}")

    # 数据库优化与WAL截断，确保文件体积实际下降
    try:
        logger.debug("开始数据库优化")
        analyze_database()
        # 先尝试检查点并截断 WAL，随后 VACUUM 收缩主库
        try:
            from sqlalchemy import text
            from core.db_factory import get_engine
            with get_engine().connect() as conn:
                try:
                    logger.debug("尝试 TRUNCATE WAL checkpoint")
                    conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
                except Exception as e:
                    logger.warning(f"TRUNCATE WAL checkpoint 失败，尝试 FULL: {e}")
                    logger.debug("TRUNCATE WAL checkpoint 失败详细信息", exc_info=True)
                    conn.execute(text("PRAGMA wal_checkpoint(FULL)"))
        except Exception as we:
            logger.warning(f"WAL 截断失败（忽略）：{we}")
            logger.debug("WAL 截断失败详细信息", exc_info=True)
        vacuum_database()
        logger.debug("数据库优化完成")
    except Exception as e:
        logger.error(f"数据库优化失败: {e}")
        logger.debug("数据库优化失败详细信息", exc_info=True)
        
    logger.info("强制归档完成")
