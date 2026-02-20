import pytest
from services.audit_service import audit_service
from models.models import AuditLog
from sqlalchemy import select
import json

@pytest.mark.asyncio
async def test_audit_log_creation(db):
    """测试审计日志记录功能"""
    await audit_service.log_event(
        action="UNIT_TEST_LOGIN",
        user_id=1,
        username="tester",
        ip_address="127.0.0.1",
        details={"browser": "chrome"},
        status="success"
    )
    
    # 验证数据库记录
    result = await db.execute(select(AuditLog).filter_by(action="UNIT_TEST_LOGIN"))
    log = result.scalar_one()
    
    assert log.username == "tester"
    assert log.user_id == 1
    assert log.ip_address == "127.0.0.1"
    assert log.status == "success"
    
    # 验证详情 JSON 序列化
    details_dict = json.loads(log.details)
    assert details_dict["browser"] == "chrome"

@pytest.mark.asyncio
async def test_get_logs(db):
    """测试日志查询接口"""
    from unittest.mock import patch, AsyncMock, MagicMock
    
    # 模拟数据
    mock_logs = [MagicMock(spec=AuditLog, action=f"ACTION_{i}") for i in range(5)]
    
    with patch.object(audit_service.bridge, "list_audit_logs", new_callable=AsyncMock) as mock_list, \
         patch.object(audit_service.bridge, "query_aggregate", new_callable=AsyncMock) as mock_agg:
        
        mock_list.return_value = mock_logs
        mock_agg.return_value = [{"cnt": 5}]
        
        # 调用接口
        logs, total = await audit_service.get_logs(page=1, limit=10)
        
        assert len(logs) == 5
        assert total == 5
        assert logs[0].action == "ACTION_0"
        
        # 验证调用参数
        mock_list.assert_called_once_with(
            user_id=None,
            action=None,
            limit=10,
            offset=0
        )
        
    # 测试带筛选的调用
    with patch.object(audit_service.bridge, "list_audit_logs", new_callable=AsyncMock) as mock_list, \
         patch.object(audit_service.bridge, "query_aggregate", new_callable=AsyncMock) as mock_agg:
        
        mock_list.return_value = [mock_logs[0]]
        mock_agg.return_value = [{"cnt": 1}]
        
        logs_filtered, total_filtered = await audit_service.get_logs(action="ACTION_0")
        
        assert len(logs_filtered) == 1
        assert total_filtered == 1
        assert logs_filtered[0].action == "ACTION_0"
        
        mock_list.assert_called_once_with(
            user_id=None,
            action="ACTION_0",
            limit=50,
            offset=0
        )
