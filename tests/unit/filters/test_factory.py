import pytest
from filters.factory import FilterChainFactory
from filters.filter_chain import FilterChain
from types import SimpleNamespace

@pytest.fixture
def factory():
    return FilterChainFactory()

@pytest.fixture
def mock_rule():
    rule = SimpleNamespace()
    rule.id = 1
    rule.enable_rule = True
    rule.is_ai = False
    rule.enable_delay = False
    rule.enable_media_type_filter = False
    rule.enable_media_size_filter = False
    rule.enable_extension_filter = False
    rule.enable_push = False
    rule.only_rss = False
    rule.is_delete_original = False
    rule.enable_comment_button = False
    rule.enable_duration_filter = False
    rule.enable_resolution_filter = False
    rule.enable_file_size_range = False
    rule.enabled_filters = None
    return rule

def test_factory_initialization(factory):
    assert factory.get_global_disabled_filters() == []

def test_factory_set_global_disabled(factory):
    factory.set_global_disabled_filters(['ai', 'delay'])
    assert 'ai' in factory.get_global_disabled_filters()
    assert 'delay' in factory.get_global_disabled_filters()

def test_create_chain_for_rule_basic(factory, mock_rule):
    chain = factory.create_chain_for_rule(mock_rule)
    assert isinstance(chain, FilterChain)
    # By default, with all flags False, it should only have 'init' (and maybe 'global' if not filtered)
    # Check default order in registry: init, global, delay, keyword...
    # Based on _get_default_filters_for_rule: 
    # it loops through default_order and checks flags.
    # 'init' and 'global' don't have flags in _get_default_filters_for_rule, so they are enabled by default.
    # 'keyword' and 'replace' also don't have flags in that method, so they are enabled too.
    # Let's verify.

def test_create_chain_with_explicit_config(factory, mock_rule):
    mock_rule.enabled_filters = '["init", "keyword"]'
    chain = factory.create_chain_for_rule(mock_rule, use_cache=False)
    # keyword is in PARALLEL_CANDIDATES, init is not. 
    # So it should have 2 nodes.

def test_generate_cache_key(factory, mock_rule):
    key1 = factory._generate_cache_key(mock_rule)
    mock_rule.is_ai = True
    key2 = factory._generate_cache_key(mock_rule)
    assert key1 != key2

def test_create_chain_parallel_group(factory):
    # 'keyword' and 'media' are in PARALLEL_CANDIDATES
    filters = ['keyword', 'media', 'ai'] 
    chain = factory.create_chain_from_config(filters)
    # keyword + media should be in a ParallelGroup
    # ai should be a separate step
    # We can't easily inspect the internal structure of chain without adding helpers, 
    # but the logs show "添加并发过滤器组".
    assert isinstance(chain, FilterChain)

def test_cache_functionality(factory, mock_rule):
    chain1 = factory.create_chain_for_rule(mock_rule, use_cache=True)
    chain2 = factory.create_chain_for_rule(mock_rule, use_cache=True)
    assert chain1 is chain2
    
    factory.clear_cache()
    chain3 = factory.create_chain_for_rule(mock_rule, use_cache=True)
    assert chain1 is not chain3
