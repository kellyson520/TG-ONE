import pytest
import asyncio
import json
try:
    import yaml
except ImportError:
    yaml = None
from services.rule_management_service import RuleManagementService
from models.models import ForwardRule, Keyword, ReplaceRule, Chat

@pytest.mark.asyncio
async def test_rule_export_import(container):
    """Test Export and Import of Rules"""
    
    # 1. Setup Data: Chats (Manual DB)
    async with container.db.session() as session:
        # Create Source/Target Chats
        source = Chat(telegram_chat_id="1001", name="Source Chat", chat_type="channel")
        target = Chat(telegram_chat_id="2002", name="Target Chat", chat_type="channel")
        # Check if they exist (idempotent for re-runs if any)
        # But for tests, DB is fresh.
        session.add_all([source, target])
        await session.commit()
    
    # Initialize Service
    service = RuleManagementService()

    # 2. Create Rule via Service
    res = await service.create_rule(
        source_chat_id="1001",
        target_chat_id="2002",
        forward_mode="custom"
    )
    assert res['success'] is True
    rule_id = res['rule_id']
    
    # 3. Add Keywords via Service
    res_kw = await service.add_keywords(
        rule_id=rule_id,
        keywords=["test_key", "regex_key"], # Adding both as normal for now or verify logic
        is_regex=False
    )
    # Wait, in the original test one was regex. Service `add_keywords` adds list with SAME settings.
    # So call twice.
    # First call already done.
    
    await service.add_keywords(rule_id, ["test_key"], is_regex=False)
    await service.add_keywords(rule_id, ["regex_key"], is_regex=True)
    
    # 4. Add Replace Rules via Service
    await service.add_replace_rules(
        rule_id=rule_id,
        patterns=["old"],
        replacements=["new"],
        is_regex=False
    )
    
    # 2. Test JSON Export
    res = await service.export_rule_config(rule_id, format="json")
    assert res['success'] is True
    data = json.loads(res['content'])
    assert data['rule']['forward_mode'] == 'custom'
    # Check counts
    assert len(data['rule']['keywords']) == 2
    assert len(data['rule']['replace_rules']) == 1
    
    # 3. Test YAML Export (if available)
    if yaml:
        res_yaml = await service.export_rule_config(rule_id, format="yaml")
        assert res_yaml['success'] is True
        data_yaml = yaml.safe_load(res_yaml['content'])
        assert data_yaml['rule']['forward_mode'] == 'custom'
    
    # 4. Test Import (Modify and Import Back)
    # Modify data
    data['rule']['keywords'].append({"k": "new_imported_key", "rx": False, "bl": True})
    data['rule']['replace_rules'].append({"p": "foo", "c": "bar", "rx": False})
    
    import_content = json.dumps(data)
    
    # Import into same rule (should append)
    import_res = await service.import_rule_config(rule_id, import_content, format="json")
    assert import_res['success'] is True
    
    # Verify DB
    async with container.db.session() as session:
        # Use direct query to bypass session cache if needed
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        stmt = select(ForwardRule).options(selectinload(ForwardRule.keywords), selectinload(ForwardRule.replace_rules)).filter_by(id=rule_id)
        rule_updated = (await session.execute(stmt)).scalar_one()
        
        kw_texts = [k.keyword for k in rule_updated.keywords]
        assert "new_imported_key" in kw_texts
        assert "test_key" in kw_texts
        assert len(rule_updated.keywords) == 3
        
        rr_patterns = [r.pattern for r in rule_updated.replace_rules]
        assert "foo" in rr_patterns
        assert len(rule_updated.replace_rules) == 2
