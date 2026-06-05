import pytest
from filters.registry import FilterRegistry, BaseFilter

class MockFilter(BaseFilter):
    """Mock Filter Description"""
    async def _process(self, context):
        return True

def test_registry_initialization():
    registry = FilterRegistry()
    assert len(registry.get_all_filters()) >= 16
    assert registry.get_filter('init') is not None
    assert 'init' in registry.get_default_order()

def test_registry_register_custom():
    registry = FilterRegistry()
    registry.register('custom', MockFilter)
    assert registry.get_filter('custom') == MockFilter
    assert isinstance(registry.create_filter('custom'), MockFilter)

def test_registry_register_invalid_type():
    registry = FilterRegistry()
    with pytest.raises(TypeError):
        registry.register('invalid', dict) # type: ignore

def test_registry_validate_config():
    registry = FilterRegistry()
    # Test valid
    valid, errors = registry.validate_filter_config(['init', 'keyword'])
    assert valid is True
    assert len(errors) == 0
    
    # Test unknown
    valid, errors = registry.validate_filter_config(['unknown'])
    assert valid is False
    assert "未知的过滤器: unknown" in errors
    
    # Test dependency
    valid, errors = registry.validate_filter_config(['reply']) # depends on sender
    assert valid is False
    assert any("依赖于 sender" in e for e in errors)

def test_registry_optimize_order():
    registry = FilterRegistry()
    # out of order input
    input_filters = ['push', 'init', 'keyword']
    ordered = registry.optimize_filter_order(input_filters)
    # expected order: init, keyword, push
    assert ordered == ['init', 'keyword', 'push']

def test_get_filter_info():
    registry = FilterRegistry()
    registry.register('mock', MockFilter)
    info = registry.get_filter_info()
    assert 'mock' in info
    assert info['mock']['class_name'] == 'MockFilter'
    assert info['mock']['description'] == "Mock Filter Description"
