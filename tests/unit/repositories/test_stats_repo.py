import pytest
from sqlalchemy import select, func
from repositories.stats_repo import StatsRepository
from models.models import RuleLog, RuleStatistics
from core.container import container
from datetime import date

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestStatsRepository:
    @pytest.fixture
    def repo(self):
        return StatsRepository(container.db)

    async def test_log_action_buffered(self, repo, db):
        # 记录 5 条日志
        for i in range(5):
            await repo.log_action(rule_id=1, msg_id=100+i, status="success", result="OK")
        
        # 此时 DB 应该还没有数据 (buffer size < 100)
        stmt = select(func.count(RuleLog.id))
        count = (await db.execute(stmt)).scalar()
        assert count == 0
        
        # 手动刷回
        await repo.flush_logs()
        
        count = (await db.execute(stmt)).scalar()
        assert count == 5

    async def test_increment_rule_stats(self, repo, db):
        # 第一次增加 (应触发 insert)
        await repo.increment_rule_stats(rule_id=10, status="success")
        
        today = date.today().isoformat()
        stmt = select(RuleStatistics).filter_by(rule_id=10, date=today)
        res = await db.execute(stmt)
        stat = res.scalar_one()
        assert stat.forwarded_count == 1
        assert stat.processed_count == 1
        
        # 第二次增加 (应触发 update)
        await repo.increment_rule_stats(rule_id=10, status="error")
        await db.refresh(stat)
        assert stat.forwarded_count == 1
        assert stat.error_count == 1
        assert stat.processed_count == 2

    async def test_get_rules_stats_batch(self, repo, db):
        # 准备数据
        today = date.today()
        s1 = RuleStatistics(rule_id=1, date=today.isoformat(), forwarded_count=10, processed_count=12)
        s2 = RuleStatistics(rule_id=2, date=today.isoformat(), forwarded_count=5, processed_count=5)
        db.add_all([s1, s2])
        await db.commit()
        
        stats = await repo.get_rules_stats_batch([1, 2, 3])
        assert stats[1]["forwarded"] == 10
        assert stats[2]["forwarded"] == 5
        assert stats[3]["forwarded"] == 0 # 缺失填充
