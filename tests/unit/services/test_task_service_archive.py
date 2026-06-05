"""
P6-1/P6-2: TaskService 与 UnifiedQueryBridge 集成测试
验证服务层调用桥接器获取热冷数据的能力。
"""
import pytest
import os
import sys
import json
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from services.task_service import TaskService


class TestTaskServiceArchive:

    @pytest.fixture
    def task_service(self):
        with patch("services.task_service.container") as mock_container:
            # 模拟数据库 Session，虽然 TaskService 的新方法不直接用它，但其他旧方法可能用
            mock_session = AsyncMock()
            mock_container.db.get_session.return_value.__aenter__.return_value = mock_session
            
            # 这里的 bridge 不需要 mock，因为我们要测试集成
            # 但我们需要 mock bridge 的依赖 (DuckDB/SQLite 路径)
            with patch("core.archive.bridge.settings") as mock_settings:
                mock_settings.DB_PATH = "sqlite+aiosqlite:///data/db/forward.db"
                mock_settings.ARCHIVE_QUERY_DEBUG = False
                
                service = TaskService()
                return service

    @pytest.mark.asyncio
    async def test_list_tasks_unified(self, task_service):
        """测试 list_tasks 成功合并热冷数据结果并正确解析字段"""
        # 准备 Mock 数据返回给 bridge
        mock_rows = [
            {
                "id": 1, 
                "status": "completed", 
                "task_data": json.dumps({"forwarded": 10, "total": 10}),
                "forwarded_count": 10,
                "total_count": 10,
                "started_at": "2026-02-18 10:00:00"
            },
            {
                "id": 100, 
                "status": "completed", 
                "task_data": json.dumps({"forwarded": 5}), # 旧数据可能字段不全
                "forwarded_count": None,
                "total_count": 10,
                "started_at": "2026-01-01 10:00:00"
            }
        ]

        # 模拟 bridge.list_tasks
        task_service.bridge.list_tasks = AsyncMock(return_value=mock_rows)

        result = await task_service.list_tasks(limit=10)

        assert result["success"] is True
        assert len(result["tasks"]) == 2
        
        # 验证第一个任务 (热数据，字段完整)
        t1 = result["tasks"][0]
        assert t1["id"] == 1
        assert t1["forwarded"] == 10
        
        # 验证第二个任务 (冷数据，使用 fallback 逻辑)
        t2 = result["tasks"][1]
        assert t2["id"] == 100
        assert t2["forwarded"] == 5 # 从 JSON 解析

    @pytest.mark.asyncio
    async def test_get_task_detail_unified(self, task_service):
        """测试 get_task_detail 跨层查询能力"""
        mock_row = {
            "id": 123,
            "status": "processing",
            "task_data": json.dumps({"source_chat_id": "-1001"}),
            "done_count": 50,
            "total_count": 100,
            "forwarded_count": 30,
            "filtered_count": 15,
            "failed_count": 5,
            "last_message_id": 999,
            "source_chat_id": "-1001",
            "target_chat_id": "-1002"
        }

        task_service.bridge.get_task_detail = AsyncMock(return_value=mock_row)

        result = await task_service.get_task_detail(task_id=123)

        assert result["success"] is True
        task = result["task"]
        assert task["id"] == 123
        assert task["data"]["done"] == 50
        assert task["data"]["source_chat_id"] == "-1001"

    @pytest.mark.asyncio
    async def test_list_tasks_error_handling(self, task_service):
        """测试当桥接器查询抛出异常时的处理"""
        task_service.bridge.list_tasks = AsyncMock(side_effect=Exception("Bridge failure"))

        result = await task_service.list_tasks()

        assert result["success"] is False
        assert "Bridge failure" in result["error"]
        assert result["tasks"] == []
