import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from datetime import datetime, timedelta

# 在导入 session_service 前 Mock 掉它内部依赖的模块
# 避免导入 session_management 导致触发 tombstone 逻辑
sys.modules["handlers.button.session_management"] = MagicMock()
from services.session_service import SessionService

class TestSessionService:
    @pytest.fixture
    def service(self):
        return SessionService()

    @pytest.fixture
    def mock_session_manager(self):
        # 注意：SessionService 中的一些方法使用了 await，而一些方法由于底层 SessionManager 实现的原因没有使用 await。
        # 这里使用 AsyncMock，对于同步调用的方法，我们需要明确设置其为非协程返回值。
        with patch("handlers.button.session_management.session_manager", new_callable=AsyncMock) as mock:
            # 识别同步调用并设置 return_value 为普通值
            # SessionService 中以下方法是通过类似 session_manager.get_time_range(user_id) 调用的
            mock.get_time_range = MagicMock() 
            mock.get_delay_setting = MagicMock()
            mock.set_time_range = MagicMock()
            mock.set_delay_setting = MagicMock()
            
            # 以下是通过 await 调用的
            mock.get_history_progress = AsyncMock()
            mock.get_selected_rule = AsyncMock()
            mock.set_selected_rule = AsyncMock()
            mock.start_history_task = AsyncMock()
            mock.stop_history_task = AsyncMock()
            
            yield mock

    @pytest.fixture
    def mock_rule_service(self):
        with patch("services.rule_management_service.rule_management_service", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_get_history_task_status_no_task(self, service, mock_session_manager):
        # 模拟没有运行中的任务 (await 调用)
        mock_session_manager.get_history_progress.return_value = None
        
        result = await service.get_history_task_status(123)
        assert result["has_task"] is False
        assert "没有运行的历史任务" in result["message"]

    @pytest.mark.asyncio
    async def test_get_history_task_status_running(self, service, mock_session_manager):
        # 模拟运行中的任务 (await 调用)
        start_time = (datetime.now() - timedelta(minutes=10)).isoformat()
        mock_session_manager.get_history_progress.return_value = {
            "status": "running",
            "total": 100,
            "done": 50,
            "forwarded": 30,
            "filtered": 15,
            "failed": 5,
            "start_time": start_time
        }
        
        result = await service.get_history_task_status(123)
        assert result["has_task"] is True
        assert result["status"] == "running"
        assert result["progress"]["percentage"] == 50.0
        assert result["estimated_remaining"] is not None

    @pytest.mark.asyncio
    async def test_get_selected_rule_success(self, service, mock_session_manager, mock_rule_service):
        mock_session_manager.get_selected_rule.return_value = 1
        mock_rule_service.get_rule_detail.return_value = {
            "success": True,
            "source_chat": "Source Group",
            "target_chat": "Target Group",
            "enabled": True,
            "enable_dedup": False
        }
        
        result = await service.get_selected_rule(123)
        assert result["has_selection"] is True
        assert result["rule"]["id"] == 1
        assert result["rule"]["source_chat"]["title"] == "Source Group"

    @pytest.mark.asyncio
    async def test_get_selected_rule_none(self, service, mock_session_manager):
        mock_session_manager.get_selected_rule.return_value = None
        
        result = await service.get_selected_rule(123)
        assert result["has_selection"] is False
        assert "请先选择一个转发规则" in result["message"]

    @pytest.mark.asyncio
    async def test_update_time_range(self, service, mock_session_manager):
        # 模拟同步调用
        mock_session_manager.get_time_range.return_value = {"start_year": 2024}
        
        result = await service.update_time_range(123, end_year=2025)
        assert result["success"] is True
        mock_session_manager.set_time_range.assert_called_once()
        # 验证合并逻辑
        args = mock_session_manager.set_time_range.call_args[0]
        assert args[1]["start_year"] == 2024
        assert args[1]["end_year"] == 2025

    @pytest.mark.asyncio
    async def test_get_delay_settings(self, service, mock_session_manager):
        # 模拟同步调用
        mock_session_manager.get_delay_setting.return_value = 125 # 2分5秒
        
        result = await service.get_delay_settings(123)
        assert result["success"] is True
        assert result["delay_seconds"] == 125
        assert result["delay_text"] == "2分5秒"

    @pytest.mark.asyncio
    async def test_start_history_task_no_selection(self, service, mock_session_manager, mock_rule_service):
        # 模拟没有选择规则的情况 (await 调用)
        mock_session_manager.get_selected_rule.return_value = None
        
        result = await service.start_history_task(123)
        assert result["success"] is False
        assert "请先选择一个转发规则" in result["error"]

    @pytest.mark.asyncio
    async def test_start_history_task_success(self, service, mock_session_manager, mock_rule_service):
        # 准备 Mock
        mock_session_manager.get_selected_rule.return_value = 1
        mock_rule_service.get_rule_detail.return_value = {"success": True}
        # get_time_range 是同步调用
        mock_session_manager.get_time_range.return_value = {"start_year": 2024}
        mock_session_manager.start_history_task.return_value = {
            "success": True,
            "task_id": "task_abc",
            "message": "任务已启动"
        }
        
        result = await service.start_history_task(123)
        assert result["success"] is True
        assert result["task_id"] == "task_abc"

    def test_calculate_estimated_time(self, service):
        start_time = (datetime.now() - timedelta(seconds=100)).isoformat()
        progress = {
            "total": 1000,
            "done": 10,
            "start_time": start_time
        }
        # 速度 = 10条/100秒 = 0.1条/秒
        # 剩余 = 990条 / 0.1 = 9900秒 = 165分钟 = 2.75小时
        time_text = service._calculate_estimated_time(progress)
        assert "小时" in time_text or "分钟" in time_text
