import pytest
from unittest.mock import AsyncMock, patch
from services.forward_service import ForwardService
from sqlalchemy import select
from models.models import ForwardRule, Chat

@pytest.mark.asyncio
class TestForwardService:
    @pytest.fixture
    def service(self):
        return ForwardService()

    async def test_get_forward_stats_empty(self, service):
        # Patch services.analytics_service.analytics_service which is used inside the method
        with patch("services.analytics_service.analytics_service.get_daily_summary", new_callable=AsyncMock) as mock_summary:
            mock_summary.return_value = {}
            
            stats = await service.get_forward_stats()
            assert stats["today"]["total_forwards"] == 0
            assert stats["trend"]["direction"] == "new"

    async def test_get_forward_stats_with_data(self, service):
        with patch("services.analytics_service.analytics_service.get_daily_summary", new_callable=AsyncMock) as mock_summary:
            # 模拟今日和昨日数据
            mock_summary.side_effect = [
                {"total_forwards": 100, "total_size_bytes": 1024, "chats": {"chat1": 50}, "active_chats": 1}, # 今日
                {"total_forwards": 50} # 昨日
            ]
            
            stats = await service.get_forward_stats()
            assert stats["today"]["total_forwards"] == 100
            assert stats["yesterday"]["total_forwards"] == 50
            assert stats["trend"]["percentage"] == 100.0
            assert stats["trend"]["direction"] == "up"

    async def test_get_forward_rules(self, service, db):
        # 1. 准备数据
        c1 = Chat(telegram_chat_id="1001", name="Source")
        c2 = Chat(telegram_chat_id="1002", name="Target")
        db.add_all([c1, c2])
        await db.commit()
        await db.refresh(c1)
        await db.refresh(c2)
        
        rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id)
        db.add(rule)
        await db.commit()
        
        # 2. 测试查询
        result = await service.get_forward_rules()
        assert result["total_count"] >= 1
        assert len(result["rules"]) >= 1
        assert result["rules"][0]["source_chat_id"] == "1001"

    async def test_create_forward_rule(self, service, db):
        c1 = Chat(telegram_chat_id="2001", name="Source")
        c2 = Chat(telegram_chat_id="2002", name="Target")
        db.add_all([c1, c2])
        await db.commit()
        
        result = await service.create_forward_rule(2001, 2002, use_bot=False)
        assert result["success"] is True
        assert "rule_id" in result
        
        # 验证数据库
        res = await db.execute(select(ForwardRule).filter_by(id=result["rule_id"]))
        rule = res.scalar_one()
        assert rule.use_bot is False

    async def test_update_delete_forward_rule(self, service, db):
        c1 = Chat(telegram_chat_id="3001")
        c2 = Chat(telegram_chat_id="3002")
        db.add_all([c1, c2])
        await db.commit()
        
        rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id, enable_rule=True)
        db.add(rule)
        await db.commit()
        
        # 更新
        await service.update_forward_rule(rule.id, enable_rule=False)
        await db.refresh(rule)
        assert rule.enable_rule is False
        
        # 删除
        del_res = await service.delete_forward_rule(rule.id)
        assert del_res["success"] is True
        
        res = await db.execute(select(ForwardRule).filter_by(id=rule.id))
        assert res.scalar_one_or_none() is None
