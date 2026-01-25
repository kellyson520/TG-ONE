import pytest
import json
from sqlalchemy import select, func
from repositories.task_repo import TaskRepository
from models.models import TaskQueue
from core.container import container
from datetime import datetime, timedelta

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestTaskRepository:
    @pytest.fixture
    def repo(self):
        return TaskRepository(container.db)

    async def test_push_and_deduplication(self, repo, db):
        payload = {"chat_id": 1, "message_id": 100}
        
        # 第一次 push
        await repo.push("forward", payload)
        
        # 验证
        stmt = select(TaskQueue).filter_by(unique_key="forward:1:100")
        res = await db.execute(stmt)
        task = res.scalar_one()
        assert task.task_type == "forward"
        
        # 第二次 push (应被去重)
        await repo.push("forward", payload)
        
        # 再次查总数，应该还是1
        stmt_count = select(func.count(TaskQueue.id))
        count = (await db.execute(stmt_count)).scalar()
        assert count == 1

    async def test_fetch_next_order_and_status(self, repo, db):
        # 插入两个任务，一个优先级高
        await repo.push("low", {"id": 1}, priority=0)
        await repo.push("high", {"id": 2}, priority=10)
        
        # 拉取第一个
        task = await repo.fetch_next()
        assert task is not None
        assert task.task_type == "high"
        assert task.status == "running"
        assert task.started_at is not None
        
        # 再次拉取
        task2 = await repo.fetch_next()
        assert task2.task_type == "low"

    async def test_complete_and_fail(self, repo, db):
        await repo.push("task", {"id": 1})
        task = await repo.fetch_next()
        tid = task.id
        
        # 完成
        await repo.complete(tid)
        # 重新获取以验证
        task = await db.get(TaskQueue, tid)
        assert task.status == "completed"
        assert task.completed_at is not None
        
        # 试图从 completed 转到 failed (应失败或警告，不改变状态)
        await repo.fail(tid, "error")
        await db.refresh(task) # 这个现在可以了，因为 task 是从 db 加载的
        assert task.status == "completed"

    async def test_fail_or_retry(self, repo, db):
        await repo.push("retry_task", {"id": 1})
        task = await repo.fetch_next()
        tid = task.id
        
        # 第一次失败 -> 重试 (pending)
        await repo.fail_or_retry(tid, "error 1", max_retries=3)
        task = await db.get(TaskQueue, tid)
        assert task.status == "pending"
        assert task.retry_count == 1
        assert task.next_retry_at > datetime.utcnow()
        
        # 模拟达到最大重试
        task.retry_count = 3
        await db.commit()
        await repo.fail_or_retry(tid, "final error", max_retries=3)
        await db.refresh(task)
        assert task.status == "failed"

    async def test_rescue_stuck_tasks(self, repo, db):
        # 插入一个卡住的任务 (status=running, updated_at 很久以前)
        old_time = datetime.utcnow() - timedelta(minutes=20)
        task = TaskQueue(
            task_type="stuck",
            task_data="{}",
            status="running",
            updated_at=old_time
        )
        db.add(task)
        await db.commit()
        tid = task.id
        
        rescued = await repo.rescue_stuck_tasks(timeout_minutes=10)
        assert rescued == 1
        
        await db.refresh(task)
        assert task.status == "pending"
        assert task.retry_count == 1
