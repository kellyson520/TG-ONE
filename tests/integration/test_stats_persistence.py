import pytest
import asyncio
from repositories.stats_repo import StatsRepository
from models.models import RuleLog
from sqlalchemy import select, func

@pytest.mark.asyncio
async def test_stats_buffering_and_flush(container):
    """Test StatsRepository buffering and flushing mechanism"""
    
    # Initialize Repo with actual container db reference
    repo = StatsRepository(container.db)
    # Ensure buffer is empty
    repo._log_buffer = []
    
    # 1. Start Flush Task
    await repo.start()
    
    # 2. Log Actions (Buffered)
    # Log 50 items (below threshold 100)
    for i in range(50):
        await repo.log_action(rule_id=1, msg_id=i, status="success")
    
    # Verify DB is empty (buffered)
    # Wait a bit to ensure async append didn't trigger flush (it shouldn't)
    await asyncio.sleep(0.1)
    
    async with container.db.session() as session:
        count = (await session.execute(select(func.count(RuleLog.id)))).scalar()
        # NOTE: If cron runs every 5s, it shouldn't have run yet.
        assert count == 0, "Should be buffered, not flushed yet"
    
    # 3. Trigger Force Flush via Stop
    await repo.stop()
    
    # 4. Verify DB has items
    async with container.db.session() as session:
        count = (await session.execute(select(func.count(RuleLog.id)))).scalar()
        assert count == 50, "All logs should be flushed after stop"
        
    # 5. Test Threshold Flush
    # Restart
    await repo.start()
    # Log 110 items (Trigger threshold 100)
    for i in range(110):
        await repo.log_action(rule_id=1, msg_id=1000+i, status="success")
        
    # Give it a moment for the async flush task to spawn and run
    await asyncio.sleep(0.5)
    
    async with container.db.session() as session:
        count = (await session.execute(select(func.count(RuleLog.id)))).scalar()
        # Should have flushed at least 100, maybe all 110 if second batch was fast
        assert count >= 150 # 50 old + 100 new
        
    await repo.stop()
