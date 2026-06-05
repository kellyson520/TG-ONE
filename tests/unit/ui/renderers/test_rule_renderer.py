import pytest
from ui.renderers.rule_renderer import RuleRenderer

@pytest.fixture
def renderer():
    return RuleRenderer()

def test_render_rule_list_empty(renderer):
    data = {'rules': [], 'pagination': {}}
    result = renderer.render_rule_list(data)
    
    assert '暂无转发规则' in result['text']
    assert len(result['buttons']) > 0

def test_render_rule_list_with_items(renderer):
    rules = [
        {'id': 1, 'source_chat': {'title': 'Src'}, 'target_chat': {'title': 'Dst'}, 'enabled': True},
        {'id': 2, 'source_chat': {'title': 'Src2'}, 'target_chat': {'title': 'Dst2'}, 'enabled': False},
    ]
    data = {
        'rules': rules,
        'pagination': {'page': 0, 'total_pages': 1, 'total_count': 2}
    }
    result = renderer.render_rule_list(data)
    
    assert 'Src' in result['text']
    assert 'Dst2' in result['text']
    assert '规则 1 | 运行' in result['text']
    assert len(result['buttons']) > 0

def test_render_rule_detail(renderer):
    rule = {
        'id': 123,
        'source_chat': {'title': 'MySource', 'telegram_chat_id': '1001'},
        'target_chat': {'title': 'MyTarget', 'telegram_chat_id': '2002'},
        'settings': {'enabled': True, 'enable_dedup': True, 'dedup_time_window_hours': 12},
        'keywords_count': 2,
        'replace_rules_count': 1,
        'enabled': True
    }
    data = {'rule': rule}
    result = renderer.render_rule_detail(data)
    
    assert '123' in result['text']
    assert 'MySource' in result['text']
    assert 'MyTarget' in result['text']
    assert '2个 / 1条' in result['text']
    assert len(result['buttons']) > 0
