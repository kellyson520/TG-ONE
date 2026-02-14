import pytest
from sqlalchemy import select, update
from repositories.task_repo import TaskRepository
from models.models import TaskQueue
from core.container import container
from datetime import datetime, timedelta
import asyncio

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestTaskRepositoryExtended:
    @pytest.fixture
    def repo(self):
        return TaskRepository(container.db)

    async def test_fetch_next_concurrency_simulation(self, repo, db):
        # Insert multiple tasks causing potential race conditions if not handled
        # Group 1: 3 tasks
        await repo.push("group1", {"id": 1, "grouped_id": "g1"}, priority=10)
        await repo.push("group1", {"id": 2, "grouped_id": "g1"}, priority=10)
        await repo.push("group1", {"id": 3, "grouped_id": "g1"}, priority=10)
        
        # Group 2: 2 tasks
        await repo.push("group2", {"id": 4, "grouped_id": "g2"}, priority=5)
        await repo.push("group2", {"id": 5, "grouped_id": "g2"}, priority=5)
        
        # Single tasks
        await repo.push("single", {"id": 6}, priority=8)
        
        # Fetch 1 task, should get all of group 1
        tasks1 = await repo.fetch_next(limit=1)
        assert len(tasks1) == 3
        ids1 = sorted([t.id for t in tasks1])
        # DB IDs might not be 1,2,3... but we can check grouping
        assert tasks1[0].grouped_id == "g1"
        
        # Check status in DB
        stmt = select(TaskQueue).where(TaskQueue.grouped_id == "g1")
        res = await db.execute(stmt)
        group1_tasks = res.scalars().all()
        for t in group1_tasks:
            assert t.status == "running"
            
        # Fetch next, should get single task (priority 8)
        tasks2 = await repo.fetch_next(limit=1)
        assert len(tasks2) == 1
        assert tasks2[0].task_type == "single"
        
        # Fetch next, should get group 2
        tasks3 = await repo.fetch_next(limit=1)
        assert len(tasks3) == 2
        assert tasks3[0].grouped_id == "g2"
        
    async def test_fetch_next_mixed_status(self, repo, db):
        # Insert tasks where some are running (stuck/expired) and some pending in same group
        # This shouldn't normally happen if lock is perfect, but good to test recovery
        
        now = datetime.utcnow()
        expired = now - timedelta(minutes=20)
        
        # Task 1 in group 3: Running but expired lock
        task1 = TaskQueue(
            task_type="mixed",
            task_data='{"id": 1, "grouped_id": "g3"}',
            grouped_id="g3",
            priority=10,
            status="running",
            locked_until=expired,
            created_at=now
        )
        db.add(task1)
        
        # Task 2 in group 3: Pending
        task2 = TaskQueue(
            task_type="mixed",
            task_data='{"id": 2, "grouped_id": "g3"}',
            grouped_id="g3",
            priority=10,
            status="pending",
            created_at=now
        )
        db.add(task2)
        await db.commit()
        
        # Fetch next should pick up both because one is pending and one is expired running
        tasks = await repo.fetch_next(limit=1)
        assert len(tasks) == 2
        assert tasks[0].grouped_id == "g3"
        assert tasks[0].status == "running"
        assert tasks[0].locked_until > now # Lock refreshed

