"""
Database Migration: Add Compression Support
添加压缩字段到相关表
"""
import asyncio
import logging
from sqlalchemy import text
from core.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_compression_fields():
    """添加压缩标志字段到数据库"""
    
    # 使用共享引擎
    from core.db_factory import get_async_engine
    engine = get_async_engine()
    db = Database(engine=engine)
    
    logger.info("=" * 60)
    logger.info("Database Migration: Adding Compression Fields")
    logger.info("=" * 60)
    
    migrations = [
        # RSSConfig table
        "ALTER TABLE rss_configs ADD COLUMN is_description_compressed BOOLEAN DEFAULT 0",
        "ALTER TABLE rss_configs ADD COLUMN is_prompt_compressed BOOLEAN DEFAULT 0",
        
        # RuleLog table
        "ALTER TABLE rule_logs ADD COLUMN is_result_compressed BOOLEAN DEFAULT 0",
        
        # ErrorLog table
        "ALTER TABLE error_logs ADD COLUMN is_traceback_compressed BOOLEAN DEFAULT 0",
    ]
    
    async with db.engine.begin() as conn:
        for sql in migrations:
            try:
                await conn.execute(text(sql))
                logger.info(f"✅ Executed: {sql}")
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    logger.info(f"⏭️  Skipped (already exists): {sql}")
                else:
                    logger.error(f"❌ Failed: {sql}")
                    logger.error(f"   Error: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Migration Completed")
    logger.info("=" * 60)
    
    await db.close()


async def compress_existing_data():
    """压缩现有的大文本数据"""
    from core.db_factory import get_async_engine
    from models.models import RSSConfig, RuleLog, ErrorLog
    from services.compression_service import compression_service
    from sqlalchemy import select
    
    engine = get_async_engine()
    db = Database(engine=engine)
    
    logger.info("\n" + "=" * 60)
    logger.info("Compressing Existing Data")
    logger.info("=" * 60)
    
    # Compress RSSConfig descriptions
    logger.info("\n1. Compressing RSSConfig descriptions...")
    async with db.session() as session:
        stmt = select(RSSConfig).where(
            RSSConfig.is_description_compressed == False,
            RSSConfig.rule_description.isnot(None)
        )
        result = await session.execute(stmt)
        configs = result.scalars().all()
        
        compressed_count = 0
        for config in configs:
            if config.rule_description and compression_service.should_compress(config.rule_description):
                compressed_data = compression_service.compress(config.rule_description)
                config.rule_description = compressed_data.decode('latin1')  # Store as string
                config.is_description_compressed = True
                compressed_count += 1
        
        if compressed_count > 0:
            await session.commit()
            logger.info(f"   ✅ Compressed {compressed_count} RSSConfig descriptions")
        else:
            logger.info(f"   ⏭️  No large descriptions to compress")
    
    # Compress RSSConfig prompts
    logger.info("\n2. Compressing RSSConfig prompts...")
    async with db.session() as session:
        stmt = select(RSSConfig).where(
            RSSConfig.is_prompt_compressed == False,
            RSSConfig.ai_extract_prompt.isnot(None)
        )
        result = await session.execute(stmt)
        configs = result.scalars().all()
        
        compressed_count = 0
        for config in configs:
            if config.ai_extract_prompt and compression_service.should_compress(config.ai_extract_prompt):
                compressed_data = compression_service.compress(config.ai_extract_prompt)
                config.ai_extract_prompt = compressed_data.decode('latin1')
                config.is_prompt_compressed = True
                compressed_count += 1
        
        if compressed_count > 0:
            await session.commit()
            logger.info(f"   ✅ Compressed {compressed_count} RSSConfig prompts")
        else:
            logger.info(f"   ⏭️  No large prompts to compress")
    
    # Compress RuleLog results (only recent large ones)
    logger.info("\n3. Compressing RuleLog results (last 1000 entries)...")
    async with db.session() as session:
        stmt = select(RuleLog).where(
            RuleLog.is_result_compressed == False,
            RuleLog.result.isnot(None)
        ).order_by(RuleLog.id.desc()).limit(1000)
        
        result = await session.execute(stmt)
        logs = result.scalars().all()
        
        compressed_count = 0
        for log in logs:
            if log.result and compression_service.should_compress(log.result):
                compressed_data = compression_service.compress(log.result)
                log.result = compressed_data.decode('latin1')
                log.is_result_compressed = True
                compressed_count += 1
        
        if compressed_count > 0:
            await session.commit()
            logger.info(f"   ✅ Compressed {compressed_count} RuleLog results")
        else:
            logger.info(f"   ⏭️  No large results to compress")
    
    # Compress ErrorLog tracebacks (only recent ones)
    logger.info("\n4. Compressing ErrorLog tracebacks (last 500 entries)...")
    async with db.session() as session:
        stmt = select(ErrorLog).where(
            ErrorLog.is_traceback_compressed == False,
            ErrorLog.traceback.isnot(None)
        ).order_by(ErrorLog.id.desc()).limit(500)
        
        result = await session.execute(stmt)
        errors = result.scalars().all()
        
        compressed_count = 0
        for error in errors:
            if error.traceback and compression_service.should_compress(error.traceback):
                compressed_data = compression_service.compress(error.traceback)
                error.traceback = compressed_data.decode('latin1')
                error.is_traceback_compressed = True
                compressed_count += 1
        
        if compressed_count > 0:
            await session.commit()
            logger.info(f"   ✅ Compressed {compressed_count} ErrorLog tracebacks")
        else:
            logger.info(f"   ⏭️  No large tracebacks to compress")
    
    # Show compression stats
    stats = compression_service.get_stats()
    logger.info("\n" + "=" * 60)
    logger.info("Compression Statistics")
    logger.info("=" * 60)
    logger.info(f"Total Compressed: {stats['compressed_count']}")
    logger.info(f"Avg Compression Ratio: {stats.get('avg_compression_ratio', 1.0):.2f}x")
    logger.info(f"Space Saved: {stats.get('space_saved_bytes', 0):,} bytes ({stats.get('space_saved_percent', 0):.1f}%)")
    
    await db.close()


async def main():
    """主函数"""
    logger.info("Starting database migration for compression support...")
    
    # Step 1: Add fields
    await add_compression_fields()
    
    # Step 2: Compress existing data
    await compress_existing_data()
    
    logger.info("\n✅ Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
