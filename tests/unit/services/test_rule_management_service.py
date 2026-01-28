import pytest
from unittest.mock import AsyncMock, patch
from services.rule_management_service import rule_management_service
from models.models import ForwardRule, Chat, Keyword
from core.container import container

@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestRuleManagementService:
    async def test_get_rule_list(self, db):
        # 准备数据
        c1 = Chat(telegram_chat_id="10101", name="S")
        c2 = Chat(telegram_chat_id="10102", name="T")
        db.add_all([c1, c2])
        await db.commit()
        
        rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id)
        db.add(rule)
        await db.commit()
        
        result = await rule_management_service.get_rule_list()
        assert result["total"] >= 1
        assert len(result["rules"]) >= 1

    async def test_create_rule(self, db):
        c1 = Chat(telegram_chat_id="20201", name="S")
        c2 = Chat(telegram_chat_id="20202", name="T")
        db.add_all([c1, c2])
        await db.commit()
        
        result = await rule_management_service.create_rule("20201", "20202", use_bot=True)
        assert result["success"] is True
        
        # 验证缓存失效调用
        with patch.object(container.rule_repo, 'clear_cache') as mock_clear:
            await rule_management_service.update_rule(result["rule_id"], enable_rule=False)
            assert mock_clear.called

    async def test_bind_chat(self, db):
        # Mock container client
        mock_client = AsyncMock()
        
        # We need to mock get_or_create_chat_async since it interacts with client
        with patch("core.helpers.id_utils.get_or_create_chat_async") as mock_get_chat:
            # Setup mocks to return chat name, id, obj
            c1 = Chat(id=1, telegram_chat_id="10001", name="Source")
            c2 = Chat(id=2, telegram_chat_id="10002", name="Target")
            db.add_all([c1, c2])
            await db.commit()
            
            mock_get_chat.side_effect = [
                ("Target", "10002", c2),
                ("Source", "10001", c1)
            ]
            
            result = await rule_management_service.bind_chat(mock_client, "Source", "Target")
            
            assert result['success'] is True
            assert result['source_name'] == "Source"

    async def test_add_delete_keywords(self, db):
        c1 = Chat(telegram_chat_id="30301", name="S1")
        c2 = Chat(telegram_chat_id="30302", name="T1")
        db.add_all([c1, c2])
        await db.commit()
        rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id)
        db.add(rule)
        await db.commit()
        
        # 添加
        await rule_management_service.add_keywords(rule.id, ["apple", "banana"])
        
        # 验证
        from sqlalchemy import select
        res = await db.execute(select(Keyword).filter_by(rule_id=rule.id))
        kws = res.scalars().all()
        assert len(kws) == 2
        
        # 删除
        await rule_management_service.delete_keywords(rule.id, ["apple"])
        res = await db.execute(select(Keyword).filter_by(rule_id=rule.id))
        kws = res.scalars().all()
        assert len(kws) == 1
        assert kws[0].keyword == "banana"

    async def test_toggle_boolean_setting(self, db):
        c1 = Chat(telegram_chat_id="40401")
        c2 = Chat(telegram_chat_id="40402")
        db.add_all([c1, c2])
        await db.commit()
        rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id, enable_dedup=False)
        db.add(rule)
        await db.commit()
        
        # Toggle enable_dedup
        await rule_management_service.toggle_rule_boolean_setting(rule.id, "enable_dedup")
        await db.refresh(rule)
        assert rule.enable_dedup is True
        
        # Toggle again
        await rule_management_service.toggle_rule_boolean_setting(rule.id, "enable_dedup")
        await db.refresh(rule)
        assert rule.enable_dedup is False

    async def test_copy_rule(self, db):
        # Create source rule with keywords
        c1 = Chat(telegram_chat_id="50501", name="S2")
        c2 = Chat(telegram_chat_id="50502", name="T2")
        c3 = Chat(telegram_chat_id="50503", name="T3")
        db.add_all([c1, c2, c3])
        await db.commit()
        
        src_rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id, enable_dedup=True)
        dst_rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c3.id, enable_dedup=False)
        db.add_all([src_rule, dst_rule])
        await db.commit()
        await db.refresh(src_rule)
        await db.refresh(dst_rule)
        
        # Add keywords to source rule
        await rule_management_service.add_keywords(src_rule.id, ["fruit"])
        
        # Mock Repo cache clearing instead of internal service method
        with patch.object(container.rule_repo, 'clear_cache') as mock_clear:
            await rule_management_service.copy_rule(src_rule.id, dst_rule.id)
            assert mock_clear.called
            
        await db.refresh(dst_rule)
        assert dst_rule.enable_dedup is True 
        
        # Verify keywords copied
        from sqlalchemy import select
        res = await db.execute(select(Keyword).filter_by(rule_id=dst_rule.id))
        kws = res.scalars().all()
        assert len(kws) == 1
        assert kws[0].keyword == "fruit"
