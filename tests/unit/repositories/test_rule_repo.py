import pytest
from repositories.rule_repo import RuleRepository
from models.models import ForwardRule, Chat
from core.container import container
from sqlalchemy import select

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestRuleRepository:
    @pytest.fixture
    def repo(self):
        return RuleRepository(container.db)

    async def test_find_chat(self, repo, db):
        # 创建一个聊天
        chat = Chat(telegram_chat_id="-100123456789", name="Test Chat")
        db.add(chat)
        await db.commit()

        # 精确查找
        found = await repo.find_chat("-100123456789")
        assert found is not None
        assert found.name == "Test Chat"

        # 变体查找 (比如省略 -100)
        found_variant = await repo.find_chat("123456789")
        assert found_variant is not None
        assert found_variant.id == chat.id

    async def test_get_rules_for_source_chat(self, repo, db):
        # 创建聊天和规则
        chat = Chat(telegram_chat_id="-1001", name="Src")
        db.add(chat)
        await db.commit()
        
        target = Chat(telegram_chat_id="-1002", name="Dst")
        db.add(target)
        await db.commit()

        rule = ForwardRule(source_chat_id=chat.id, target_chat_id=target.id)
        db.add(rule)
        await db.commit()

        # 测试获取规则
        rules = await repo.get_rules_for_source_chat("-1001")
        assert len(rules) == 1
        assert rules[0].id == rule.id

        # 测试缓存 (修改数据库但不清除缓存)
        rule.enable_rule = False
        await db.commit()
        
        rules_cached = await repo.get_rules_for_source_chat("-1001")
        assert len(rules_cached) == 1 # 应该还是原来的规则列表（缓存中）

        # 清除缓存
        repo.clear_cache()
        rules_fresh = await repo.get_rules_for_source_chat("-1001")
        assert len(rules_fresh) == 1
        assert rules_fresh[0].enable_rule is False

    async def test_toggle_rule(self, repo, db):
        chat = Chat(telegram_chat_id="-1001", name="Src")
        db.add(chat)
        await db.commit()
        
        target = Chat(telegram_chat_id="-1002", name="Dst")
        db.add(target)
        await db.commit()

        rule = ForwardRule(source_chat_id=chat.id, target_chat_id=target.id, enable_rule=True)
        db.add(rule)
        await db.commit()

        new_status = await repo.toggle_rule(rule.id)
        assert new_status is False
        
        # 刷新对象
        await db.refresh(rule)
        assert rule.enable_rule is False

    async def test_get_all_standard_pagination(self, repo, db):
        # 创建多个规则
        source = Chat(telegram_chat_id="-999", name="Source")
        db.add(source)
        await db.commit()

        for i in range(10):
            target = Chat(telegram_chat_id=f"-{1000+i}", name=f"Target{i}")
            db.add(target)
            await db.commit()
            r = ForwardRule(source_chat_id=source.id, target_chat_id=target.id)
            db.add(r)
        await db.commit()

        items, total = await repo.get_all(page=1, size=5)
        assert len(items) == 5
        assert total >= 10
