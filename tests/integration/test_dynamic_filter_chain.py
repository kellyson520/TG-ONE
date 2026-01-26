
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.pipeline import Pipeline, MessageContext
from middlewares.filter import FilterMiddleware
from filters.factory import get_filter_chain_factory
from models.models import ForwardRule, Chat
from filters.base_filter import BaseFilter

# 定义 Mock 过滤器，避免依赖真实业务逻辑
class MockFilter(BaseFilter):
    def __init__(self, name=None):
        super().__init__(name)
        self.processed = False
        
    async def _process(self, context):
        self.processed = True
        if not hasattr(context.rule, 'trace_filters'):
            context.rule.trace_filters = []
        context.rule.trace_filters.append(self.name)
        return True

@pytest.fixture
def filter_registry_mock():
    # 替换全局注册中心
    from filters.registry import get_filter_registry
    registry = get_filter_registry()
    
    # 备份原始过滤器
    original_filters = registry._filters.copy()
    original_order = registry._default_order.copy()
    
    # 注册 Mock 过滤器
    registry._filters.clear()
    registry._default_order.clear()
    
    mocks = ['init', 'keyword', 'media', 'ai', 'rss']
    for name in mocks:
        registry.register(name, type(f"Mock{name.capitalize()}Filter", (MockFilter,), {}))
        registry._default_order.append(name)
        
    yield registry
    
    # 恢复
    registry._filters = original_filters
    registry._default_order = original_order
    get_filter_chain_factory().clear_cache()

@pytest.fixture
def pipeline_env(filter_registry_mock):
    pipeline = Pipeline()
    filter_mw = FilterMiddleware()
    pipeline.add(filter_mw)
    return pipeline, filter_mw

@pytest.mark.asyncio
async def test_dynamic_chain_basic(pipeline_env):
    """测试基本的动态链条组装"""
    pipeline, _ = pipeline_env
    
    # 1. 创建规则: 仅启用 Keyword
    rule = ForwardRule(id=1, enable_rule=True)
    # Mock attributes that drive factory
    rule.enable_delay = False
    rule.is_ai = False
    rule.enable_push = False
    rule.only_rss = False
    rule.is_delete_original = False
    rule.enable_comment_button = False
    rule.enable_media_type_filter = False
    # ... factory default logic will enable 'init', 'global', 'keyword' etc based on its logic
    # To test specific enabling, we rely on factory default logic.
    # Factory enables 'keyword' by default.
    
    ctx = MessageContext(client=AsyncMock(), task_id=1, chat_id=123, message_id=100, message_obj=MagicMock())
    ctx.rules = [rule]
    ctx.trace_filters = []
    
    # Execute Pipeline
    await pipeline.execute(ctx)
    
    # Verify
    # Filter names are class names: MockKeywordFilter, MockInitFilter
    trace_names = getattr(rule, 'trace_filters', [])
    assert 'MockKeywordFilter' in trace_names
    assert 'MockInitFilter' in trace_names
    assert 'MockAiFilter' not in trace_names

@pytest.mark.asyncio
async def test_dynamic_chain_ai_enabled(pipeline_env):
    """测试启用 AI 功能"""
    pipeline, _ = pipeline_env
    
    rule = ForwardRule(id=2, enable_rule=True)
    rule.is_ai = True # Enable AI
    
    # Defaults
    rule.enable_delay = False
    rule.only_rss = False
    rule.enable_comment_button = False
    rule.enable_media_type_filter = False
    
    ctx = MessageContext(client=AsyncMock(), task_id=2, chat_id=123, message_id=101, message_obj=MagicMock())
    ctx.rules = [rule]
    
    await pipeline.execute(ctx)
    
    trace_names = getattr(rule, 'trace_filters', [])
    assert 'MockAiFilter' in trace_names

@pytest.mark.asyncio
async def test_dynamic_chain_rss_only(pipeline_env):
    """测试 RSS Only 模式"""
    pipeline, _ = pipeline_env
    
    rule = ForwardRule(id=3, enable_rule=True)
    rule.only_rss = True
    
    # Defaults
    rule.is_ai = False
    rule.enable_media_type_filter = False
    
    ctx = MessageContext(client=AsyncMock(), task_id=3, chat_id=123, message_id=102, message_obj=MagicMock())
    ctx.rules = [rule]
    
    await pipeline.execute(ctx)
    
    # Init first, then RSS (since RSS is high priority? No, default order puts RSS later)
    # Check factory logic: RSS is enabled if rule.only_rss is True
    trace_names = getattr(rule, 'trace_filters', [])
    assert 'MockRssFilter' in trace_names
