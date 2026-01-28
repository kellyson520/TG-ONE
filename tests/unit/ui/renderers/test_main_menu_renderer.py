import pytest
from ui.renderers.main_menu_renderer import MainMenuRenderer

@pytest.fixture
def renderer():
    return MainMenuRenderer()

def test_render_main_menu(renderer):
    stats = {
        'today': {'total_forwards': 100, 'total_size_bytes': 1048576},
        'dedup': {'cached_signatures': 50}
    }
    result = renderer.render(stats)
    
    assert 'text' in result
    assert 'buttons' in result
    assert '100' in result['text']
    assert '50' in result['text']
    # 1048576 bytes = 1.0 MB
    assert '1.0' in result['text']
    assert len(result['buttons']) == 4

def test_render_main_menu_error(renderer):
    # Test with invalid data causing exception (simulated by passing incompatible type if possible, 
    # but here dictionary get won't fail easily. We can mock stats to raise error on access if it was an object)
    # Or just passing None might cause AttributeError inside if not handled
    
    # render() expects dict. If we pass None, expecting safe handling?
    # The code does `stats.get`, so None.get would fail if stats is None
    result = renderer.render(None) 
    assert '❌' in result['text']
    assert len(result['buttons']) == 1 # Error view usually has 1 back button

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
