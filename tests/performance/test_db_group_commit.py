"""
Performance Test: DB Group Commit vs Direct Commit
测试批量写入与单条写入的性能差异
"""
import asyncio
import time
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.db_buffer import MessageBuffer, GroupCommitCoordinator
from models.models import MediaSignature
from core.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_direct_commit(db: Database, count: int = 1000):
    """测试直接提交模式"""
    start = time.time()
    
    for i in range(count):
        async with db.session() as session:
            sig = MediaSignature(
                chat_id=str(100000 + i % 100),
                signature=f"test_sig_{i}",
                file_id=f"file_{i}",
                content_hash=f"hash_{i}",
                media_type="photo"
            )
            session.add(sig)
            await session.commit()
    
    elapsed = time.time() - start
    logger.info(f"Direct Commit: {count} records in {elapsed:.2f}s ({count/elapsed:.2f} rec/s)")
    return elapsed

async def test_group_commit(db: Database, count: int = 1000):
    """测试批量提交模式"""
    coordinator = GroupCommitCoordinator(db.session)
    await coordinator.start()

    
    start = time.time()
    
    for i in range(count):
        sig = MediaSignature(
            chat_id=str(200000 + i % 100),
            signature=f"test_sig_batch_{i}",
            file_id=f"file_batch_{i}",
            content_hash=f"hash_batch_{i}",
            media_type="photo"
        )
        await coordinator.buffer.add(sig)
    
    # Wait for final flush
    await coordinator.stop()
    
    elapsed = time.time() - start
    logger.info(f"Group Commit: {count} records in {elapsed:.2f}s ({count/elapsed:.2f} rec/s)")
    return elapsed

async def main():
    # Use in-memory DB for testing
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    db = Database(engine=engine)

    
    # Create tables
    from models.models import Base
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("=" * 60)
    logger.info("Performance Test: DB Write Optimization")
    logger.info("=" * 60)
    
    # Test with smaller count for quick validation
    test_count = 500
    
    logger.info(f"\nTest 1: Direct Commit ({test_count} records)")
    direct_time = await test_direct_commit(db, test_count)
    
    logger.info(f"\nTest 2: Group Commit ({test_count} records)")
    group_time = await test_group_commit(db, test_count)
    
    logger.info("\n" + "=" * 60)
    logger.info("Results Summary")
    logger.info("=" * 60)
    logger.info(f"Direct Commit: {direct_time:.2f}s")
    logger.info(f"Group Commit:  {group_time:.2f}s")
    logger.info(f"Speedup:       {direct_time/group_time:.2f}x faster")
    logger.info(f"Latency Reduction: {((direct_time - group_time) / direct_time * 100):.1f}%")
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
