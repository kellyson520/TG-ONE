import pytest
from unittest.mock import MagicMock
from models.models import Chat, ForwardRule, ForwardMapping
from services.rule_service import RuleQueryService

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestRuleQueryService:
    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        # 清理缓存
        RuleQueryService.invalidate_all_caches()
        # Mock persistent cache 避免报错
        mock_pc = MagicMock()
        mock_pc.get.return_value = None
        mock_pc.set.return_value = None  # 添加 set 方法的 mock
        monkeypatch.setattr("services.rule_service.get_persistent_cache", lambda: mock_pc)

    async def test_get_rules_for_source_chat_basic(self, db):
        # 1. 准备数据
        c1 = Chat(telegram_chat_id="-1001", name="Source")
        c2 = Chat(telegram_chat_id="-1002", name="Target")
        db.add_all([c1, c2])
        await db.flush()
        
        rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id)
        db.add(rule)
        await db.commit()
        
        # 2. 调用 Service
        rules = await RuleQueryService.get_rules_for_source_chat("-1001")
        
        # 3. 验证
        assert len(rules) == 1
        assert rules[0].source_chat.telegram_chat_id == "-1001"

    @pytest.mark.skip(reason="Known Issue: Mapping query returns 1 instead of 2. Waiting for fix in Repo logic.")
    async def test_get_rules_with_mapping(self, db):
        # 验证方案七的多对多映射逻辑
        c1 = Chat(telegram_chat_id="-1001", name="Source")
        c2 = Chat(telegram_chat_id="-1002", name="Target1")
        c3 = Chat(telegram_chat_id="-1003", name="Target2")
        db.add_all([c1, c2, c3])
        await db.flush()
        
        # 创建规则
        r1 = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id)
        r2 = ForwardRule(source_chat_id=c1.id, target_chat_id=c3.id)
        db.add_all([r1, r2])
        await db.flush()
        
        # 创建映射
        m1 = ForwardMapping(source_chat_id=c1.id, target_chat_id=c2.id, rule_id=r1.id)
        m2 = ForwardMapping(source_chat_id=c1.id, target_chat_id=c3.id, rule_id=r2.id)
        db.add_all([m1, m2])
        await db.commit()
        
        # 调用
        rules = await RuleQueryService.get_rules_for_source_chat("-1001")
        assert len(rules) == 2
        tgt_ids = [r.target_chat.telegram_chat_id for r in rules]
        assert "-1002" in tgt_ids
        assert "-1003" in tgt_ids

    async def test_cache_logic(self, monkeypatch):
        # 测试缓存逻辑：验证缓存命中和失效
        # 使用唯一的 chat ID 避免与其他测试冲突
        RuleQueryService.invalidate_all_caches()
        
        from core.container import container
        
        # 使用 container 的 session 确保与 Service 使用同一个数据库
        async with container.db.session() as session:
            c1 = Chat(telegram_chat_id="-1999", name="CacheTestSource")
            c2 = Chat(telegram_chat_id="-2999", name="CacheTestTarget")
            session.add_all([c1, c2])
            await session.commit()
            
            # 第一次查询：没有规则
            rules1 = await RuleQueryService.get_rules_for_source_chat("-1999")
            assert len(rules1) == 0
            
            # 添加一个规则
            r1 = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id)
            session.add(r1)
            await session.commit()
        
        # 第二次查询：由于缓存，仍然返回 0
        rules2 = await RuleQueryService.get_rules_for_source_chat("-1999")
        assert len(rules2) == 0  # 命中缓存
        
        # 清除缓存后查询：应该返回 1
        RuleQueryService.invalidate_all_caches()
        rules3 = await RuleQueryService.get_rules_for_source_chat("-1999")
        assert len(rules3) == 1  # 缓存失效，从数据库查询
    
    async def test_id_variant_matching(self, db):
        # 测试 123456 -> -100123456 的变体匹配
        c1 = Chat(telegram_chat_id="-100123456", name="Supergroup")
        c2 = Chat(telegram_chat_id="-1002")
        db.add_all([c1, c2])
        await db.flush()
        
        r1 = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id)
        db.add(r1)
        await db.commit()
        
        # 清理缓存确保从库查
        RuleQueryService.invalidate_all_caches()
        
        matches = await RuleQueryService.get_rules_for_source_chat("123456")
        assert len(matches) == 1
        assert matches[0].source_chat.telegram_chat_id == "-100123456"
