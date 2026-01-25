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
    # 插入多条数据
    for i in range(5):
        await audit_service.log_event(
            action=f"ACTION_{i}",
            username="tester"
        )
        
    # AuditService.get_logs 返回 (logs, total) 元组，使用 page 参数
    logs, total = await audit_service.get_logs(page=1, limit=10)
    assert len(logs) >= 5
    assert total >= 5
    
    # 测试筛选
    logs_filtered, total_filtered = await audit_service.get_logs(action="ACTION_0")
    assert len(logs_filtered) == 1
    assert total_filtered == 1
    assert logs_filtered[0].action == "ACTION_0"
