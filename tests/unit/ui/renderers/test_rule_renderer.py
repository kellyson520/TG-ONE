import pytest
from unittest.mock import MagicMock
from ui.renderers.rule_renderer import RuleRenderer

@pytest.fixture
def renderer():
    return RuleRenderer()

def test_render_rule_list_empty(renderer):
    data = {'rules': [], 'pagination': {}}
    result = renderer.render_rule_list(data)
    
    assert '暂无转发规则' in result['text']
    # Check buttons: 1 row for creation/stats, 1 for batch/search, 1 for filter/refresh, 1 for back
    # Wait, check code...
    # implementation: 
    # buttons.extend(...) -> 4 rows
    assert len(result['buttons']) == 5 # 1 pagination row (empty) + 4 action rows?
    # Actually code logic:
    # page_buttons (always added) -> 1 row
    # if rules: add rule_buttons (0 here)
    # extend 4 action rows
    # Total 5 rows
    assert len(result['buttons']) == 5

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
    assert '规则 1' in result['text']
    
    # 2 rule buttons (1 row) + 1 page row + 4 action rows = 6 rows
    # code: 
    # rule_buttons -> 2 buttons (2 rules) -> 1 row (since stride is 2)
    # page_buttons -> 1 row
    # extend -> 4 rows
    assert len(result['buttons']) == 6

def test_render_rule_detail(renderer):
    rule = {
        'id': 123,
        'source_chat': {'title': 'MySource', 'telegram_chat_id': '1001'},
        'target_chat': {'title': 'MyTarget', 'telegram_chat_id': '2002'},
        'settings': {'enabled': True, 'enable_dedup': True, 'dedup_time_window_hours': 12},
        'keywords': ['kw1', 'kw2'],
        'replace_rules': [{'pattern': 'a', 'replacement': 'b'}]
    }
    data = {'rule': rule}
    result = renderer.render_rule_detail(data)
    
    assert '123' in result['text']
    assert 'MySource' in result['text']
    assert 'MyTarget' in result['text']
    assert '12 小时' in result['text']
    assert 'kw1' in result['text']
    assert 'a → b' in result['text']
    
    # Buttons: 6 rows
    assert len(result['buttons']) == 6
