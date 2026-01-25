import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.rule_management_service import rule_management_service
from models.models import ForwardRule, Chat, Keyword, ReplaceRule

@pytest.mark.asyncio
class TestRuleManagementService:
    async def test_get_rule_list(self, db):
        # 准备数据
        c1 = Chat(telegram_chat_id="101", name="S")
        c2 = Chat(telegram_chat_id="102", name="T")
        db.add_all([c1, c2])
        await db.commit()
        
        rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id)
        db.add(rule)
        await db.commit()
        
        result = await rule_management_service.get_rule_list()
        assert result["total"] >= 1
        assert len(result["rules"]) >= 1

    async def test_create_rule(self, db):
        c1 = Chat(telegram_chat_id="201", name="S")
        c2 = Chat(telegram_chat_id="202", name="T")
        db.add_all([c1, c2])
        await db.commit()
        
        result = await rule_management_service.create_rule("201", "202", use_bot=True)
        assert result["success"] is True
        
        # 验证缓存失效调用
        from core.container import container
        with patch.object(container.rule_repo, 'clear_cache') as mock_clear:
            await rule_management_service.update_rule(result["rule_id"], enable_rule=False)
            assert mock_clear.called

    async def test_add_delete_keywords(self, db):
        c1 = Chat(telegram_chat_id="301")
        c2 = Chat(telegram_chat_id="302")
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

    async def test_toggle_boolean_setting(self, db):
        c1 = Chat(telegram_chat_id="401")
        c2 = Chat(telegram_chat_id="402")
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
        c1 = Chat(telegram_chat_id="501")
        c2 = Chat(telegram_chat_id="502")
        c3 = Chat(telegram_chat_id="503")
        db.add_all([c1, c2, c3])
        await db.commit()
        
        src_rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id, enable_dedup=True)
        dst_rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c3.id, enable_dedup=False)
        db.add_all([src_rule, dst_rule])
        await db.commit()
        
        # Add keywords to source rule
        await rule_management_service.add_keywords(src_rule.id, ["fruit"])
        
        # Copy src to dst
        with patch("services.rule_service.RuleQueryService.invalidate_caches_for_chat") as mock_inv:
            await rule_management_service.copy_rule(src_rule.id, dst_rule.id)
            
        await db.refresh(dst_rule)
        assert dst_rule.enable_dedup is True # Copied setting
        
        # Verify keywords copied
        from sqlalchemy import select
        res = await db.execute(select(Keyword).filter_by(rule_id=dst_rule.id))
        kws = res.scalars().all()
        assert len(kws) == 1
        assert kws[0].keyword == "fruit"
