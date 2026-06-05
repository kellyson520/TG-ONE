import pytest
import json
from datetime import datetime
from services.task_service import TaskService
from models.models import TaskQueue

@pytest.mark.asyncio
class TestTaskService:
    @pytest.fixture
    def service(self):
        return TaskService()

    async def test_list_tasks_empty(self, service):
        result = await service.list_tasks()
        assert result["success"] is True
        assert result["tasks"] == []

    async def test_list_tasks_with_data(self, service, db):
        # 1. 准备测试数据
        task1 = TaskQueue(
            task_type="history_forward",
            status="completed",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            task_data=json.dumps({
                "forwarded": 10,
                "filtered": 2,
                "failed": 0,
                "total": 12
            })
        )
        task2 = TaskQueue(
            task_type="other",
            status="running",
            started_at=datetime.utcnow(),
            task_data=json.dumps({"progress": 0.5})
        )
        db.add_all([task1, task2])
        await db.commit()

        # 2. 测试列出所有任务
        result = await service.list_tasks(limit=10)
        assert result["success"] is True
        assert len(result["tasks"]) == 2
        # 按 ID 倒序排列
        assert result["tasks"][0]["status"] == "running"
        assert result["tasks"][1]["forwarded"] == 10

        # 3. 测试按类型过滤
        result_type = await service.list_tasks(task_type="history_forward")
        assert len(result_type["tasks"]) == 1
        assert result_type["tasks"][0]["id"] == task1.id

    async def test_get_task_detail(self, service, db):
        task = TaskQueue(
            task_type="history_forward",
            status="completed",
            task_data=json.dumps({"source_chat_id": 123, "target_chat_id": 456}),
            source_chat_id=123,
            target_chat_id=456
        )
        db.add(task)
        await db.commit()

        # 1. 按 ID 查询
        result = await service.get_task_detail(task_id=task.id)
        assert result["success"] is True
        assert result["task"]["id"] == task.id
        # 兼容性：DB 存储为 String，返回可能为 String
        assert str(result["task"]["data"]["source_chat_id"]) == "123"

        # 2. 查询最新任务
        result_latest = await service.get_task_detail()
        assert result_latest["success"] is True
        assert result_latest["task"]["id"] == task.id

        # 3. 查询不存在的任务
        result_none = await service.get_task_detail(task_id=999)
        assert result_none["success"] is False
        assert result_none["error"] == "未找到任务"

    async def test_get_recent_failed_samples(self, service, db):
        task = TaskQueue(
            task_type="history_forward",
            task_data=json.dumps({
                "failed_ids": [1001, 1002, 1003]
            })
        )
        db.add(task)
        await db.commit()

        result = await service.get_recent_failed_samples(limit=2)
        assert result["success"] is True
        # 结果受 limit 限制
        assert result["failed_ids"] == [1001, 1002]
