import pytest
from ui.renderers.main_menu_renderer import MainMenuRenderer

@pytest.fixture
def renderer():
    return MainMenuRenderer()

def test_render_main_menu(renderer):
    stats = {
        'today': {'total_forwards': 100, 'total_size_bytes': 1048576, 'saved_traffic_bytes': 2097152},
        'dedup': {'cached_signatures': 50}
    }
    result = renderer.render(stats)
    
    assert 'text' in result
    assert 'buttons' in result
    assert '100' in result['text'] # Forwards
    assert '50' in result['text']  # Cached signatures
    # 1048576 bytes = 1.0 MB (Consumed)
    assert '1.0' in result['text']
    # 2097152 bytes = 2.0 MB (Saved)
    assert '2.0' in result['text']
    assert '拦截流量' in result['text']
    assert len(result['buttons']) == 4

def test_render_main_menu_error(renderer):
    # Test error handling when input is invalid (None causing AttributeError on get)
    # The renderer blindly does stats.get which fails on None, triggering except
    result = renderer.render(None) 
    # Usually returns error view with specific text
    assert '数据加载失败' in result['text'] or '系统数据暂时不可用' in result['text']
    assert len(result['buttons']) == 1 

def test_render_forward_hub_with_data(renderer):
    data = {
        'overview': {
            'total_forwards': 500,
            'total_size_bytes': 2097152, # 2MB
            'active_chats': 5
        }
    }
    result = renderer.render_forward_hub(data)
    
    assert '500' in result['text']
    assert '2.0' in result['text']
    assert '5' in result['text']
    assert len(result['buttons']) == 4

def test_render_dedup_hub(renderer):
    data = {
        'config': {'time_window_hours': 24, 'similarity_threshold': 0.85},
        'stats': {'cached_signatures': 1000, 'cached_content_hashes': 500, 'tracked_chats': 10},
        'enabled_features': ['A', 'B']
    }
    result = renderer.render_dedup_hub(data)
    
    assert '24' in result['text']
    assert '85%' in result['text']
    assert '1,000' in result['text']
    assert 'A, B' in result['text']

def test_render_faq(renderer):
    result = renderer.render_faq()
    assert '常见问题解答' in result['text']
    assert len(result['buttons']) == 1

def test_render_detailed_docs(renderer):
    result = renderer.render_detailed_docs()
    assert '详细使用文档' in result['text']
    assert len(result['buttons']) == 1
