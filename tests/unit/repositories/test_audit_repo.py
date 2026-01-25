import pytest
from repositories.audit_repo import AuditRepository
from core.container import container
from datetime import datetime, timedelta

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestAuditRepository:
    @pytest.fixture
    def repo(self):
        return AuditRepository(container.db)

    async def test_create_log(self, repo, db):
        # 创建日志
        log = await repo.create_log(
            action="TEST_ACTION",
            username="test_user",
            details={"key": "value"}
        )
        
        assert log is not None
        assert log.action == "TEST_ACTION"
        assert log.username == "test_user"
        
        # 验证数据库
        from models.models import AuditLog
        from sqlalchemy import select
        stmt = select(AuditLog).filter_by(action="TEST_ACTION")
        res = await db.execute(stmt)
        found = res.scalar_one()
        assert found.username == "test_user"

    async def test_get_logs_filters(self, repo, db):
        # 准备数据
        now = datetime.utcnow()
        await repo.create_log(action="LOGIN", username="user1", timestamp=now - timedelta(days=1))
        await repo.create_log(action="LOGOUT", username="user1", timestamp=now)
        await repo.create_log(action="LOGIN", username="user2", timestamp=now)
        
        # 1. 按动作过滤
        logs, total = await repo.get_logs(action="LOGIN")
        assert total == 2
        assert all(l.action == "LOGIN" for l in logs)
        
        # 2. 分页测试
        logs, total = await repo.get_logs(limit=1)
        assert len(logs) == 1
        assert total == 3
        
        # 3. 时间范围过滤
        start = now - timedelta(hours=1)
        logs, total = await repo.get_logs(start_date=start)
        assert total == 2 # 今天的两条
