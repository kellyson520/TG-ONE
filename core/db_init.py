import logging
from .database import Database
from models.models import Base
# 必须导入所有定义了模型的模块，否则 create_all 找不到表

logger = logging.getLogger(__name__)

async def init_db_tables(db_url: str) -> None:
    """
    异步创建所有数据库表
    """
    logger.info("Initializing database tables...")
    logger.info("Initializing database tables...")
    
    # [Pre-flight] 执行数据库健康检查与修复
    try:
        from repositories.health_check import check_and_fix_dbs_at_startup
        check_and_fix_dbs_at_startup()
    except Exception as e:
        logger.warning(f"Database health check skipped or failed: {e}")
    
    # [Fix] 优先执行数据库迁移 (Schema Migration)
    # 确保在 create_all 之前现有表结构已有新字段
    try:
        from models.models import migrate_db
        from sqlalchemy import create_engine
        
        # 构造同步 URL 用于迁移
        sync_db_url = db_url.replace('+aiosqlite', '').replace('+asyncpg', '')
        if 'sqlite' in sync_db_url and 'check_same_thread' not in sync_db_url:
            # 简单的 sqlite url 不需要额外参数，create_engine 会处理
            pass
            
        logger.info(f"Running schema migration with sync engine: {sync_db_url}")
        sync_engine = create_engine(sync_db_url)
        migrate_db(sync_engine)
        sync_engine.dispose()
        logger.info("Schema migration completed.")
    except Exception as e:
        logger.error(f"Schema migration failed: {e}")
        # 迁移失败不应完全阻断启动，尝试继续创建表

    # 异步创建表 (使用 async engine)
    try:
        db = Database(db_url)
        async with db.engine.begin() as conn:
            # run_sync 允许在异步上下文中执行同步的 DDL 操作
            await conn.run_sync(Base.metadata.create_all)
        await db.close()
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Async table creation failed: {e}")
        raise e  # 创建表失败是致命的

if __name__ == "__main__":
    import asyncio
    # 从配置读取 URL
    # 从配置读取 URL
    from core.config import settings
    # db_url = "sqlite+aiosqlite:///db/forward.db"
    db_url = settings.DATABASE_URL if settings.DATABASE_URL else "sqlite+aiosqlite:///db/forward.db"
    asyncio.run(init_db_tables(db_url))
