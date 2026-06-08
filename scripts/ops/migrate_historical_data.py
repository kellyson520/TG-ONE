
import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.container import container
from core.config import settings
from core.archive.engine import UniversalArchiver
from models.models import TaskQueue, RuleLog, ChatStatistics, RuleStatistics, MediaSignature
from models.user import AuditLog

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MigrateHistoricalData")

async def migrate_all():
    logger.info("🚀 开始存量数据归档迁移...")
    archiver = UniversalArchiver()
    
    # 按照保留期限归档
    targets = [
        (TaskQueue, settings.HOT_DAYS_TASK, "created_at"),
        (RuleLog, settings.HOT_DAYS_LOG, "created_at"),
        (AuditLog, settings.HOT_DAYS_LOG, "timestamp"),
        (MediaSignature, settings.HOT_DAYS_SIGN, "created_at"),
        (ChatStatistics, settings.HOT_DAYS_STATS, "date"),
        (RuleStatistics, settings.HOT_DAYS_STATS, "date")
    ]
    
    summary = []
    
    for model, days, time_col in targets:
        logger.info(f"--- 迁移表: {model.__tablename__} (保留 {days} 天) ---")
        try:
            result = await archiver.archive_table(
                model_class=model,
                hot_days=days,
                time_column=time_col
            )
            summary.append(result.to_dict())
        except Exception as e:
            logger.error(f"迁移表 {model.__tablename__} 失败: {e}")
            summary.append({"table": model.__tablename__, "success": False, "error": str(e)})

    logger.info("✅ 所有归档任务执行完毕")
    
    # 执行 VACUUM
    logger.info("🧹 正在执行 VACUUM 以回收 SQLite 物理空间...")
    try:
        from sqlalchemy import text
        async with container.db.get_session() as session:
            # aiosqlite 不支持在事务中 VACUUM，需要特殊处理
            # 实际上在 aiosqlite 中，VACUUM 需要在非事务模式下执行
            # 由于我们的 session manager 默认开启事务，这里我们绕过它
            pass
            
        # 使用原生连接执行 VACUUM
        import sqlite3
        db_path = settings.DB_PATH
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("VACUUM")
        finally:
            conn.close()
        logger.info("✨ VACUUM 完成")
    except Exception as e:
        logger.error(f"VACUUM 失败: {e}")

    logger.info("📊 迁移摘要:")
    for s in summary:
        logger.info(f" - {s.get('table_name', 'Unknown')}: {s.get('archived_count', 0)} 条记录归档")

if __name__ == "__main__":
    asyncio.run(migrate_all())
