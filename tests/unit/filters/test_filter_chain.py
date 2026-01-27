
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure modules are loaded so patch can find them
import filters.context
import repositories.db_context
import models.models
import core.helpers.error_handler

# Patch dependencies BEFORE importing module under test 
# (although since we just imported them, they are already loaded, 
# but we want to patch the classes/functions inside them)

with patch("filters.context.MessageContext") as MockCtx, \
     patch("repositories.db_context.async_db_session"), \
     patch("models.models.MediaSignature"), \
     patch("core.helpers.error_handler.handle_errors", side_effect=lambda **kw: lambda f: f), \
     patch("core.helpers.error_handler.log_execution", side_effect=lambda **kw: lambda f: f):
    
    from filters.filter_chain import FilterChain
    from filters.base_filter import BaseFilter

class MockFilter(BaseFilter):
    def __init__(self, name, should_continue=True, delay=0, error=None):
        # We manually set name to avoid BaseFilter init if it's problematic, 
        # but FilterChain checks isinstance(x, BaseFilter), so we must inherit.
        # super().__init__() calls self.name = ...
        self.name = name
        self.should_continue = should_continue
        self.delay = delay
        self.error = error
        
    async def _process(self, context):
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.should_continue

@pytest.fixture
def mock_db():
    with patch("filters.filter_chain.async_db_session") as db_mock, \
         patch("repositories.db_operations.DBOperations") as db_ops_mock:
        
        mock_session = AsyncMock()
        db_mock.return_value.__aenter__.return_value = mock_session
        
        mock_db_ops = AsyncMock()
        # DBOperations.create() is async, so it must return an awaitable that yields the instance
        db_ops_mock.create = AsyncMock(return_value=mock_db_ops)
        
        yield mock_session, mock_db_ops

@pytest.mark.asyncio
async def test_filter_chain_success_flow(mock_db):
    chain = FilterChain()
    chain.add_filter(MockFilter("f1"))
    chain.add_filter(MockFilter("f2"))
    
    # Mock context creation inside chain.process
    with patch("filters.filter_chain.MessageContext") as MockContext:
        res = await chain.process(None, None, None, None)
    
    assert res is True

@pytest.mark.asyncio
async def test_filter_chain_interruption(mock_db):
    chain = FilterChain()
    chain.add_filter(MockFilter("f1", should_continue=True))
    chain.add_filter(MockFilter("f2", should_continue=False))
    # f3 should NOT be called
    f3 = MockFilter("f3")
    f3._process = AsyncMock(wraps=f3._process)
    chain.add_filter(f3)
    
    with patch("filters.filter_chain.MessageContext"):
        res = await chain.process(None, None, None, None)
    
    assert res is False
    f3._process.assert_not_called()

@pytest.mark.asyncio
async def test_record_signature(mock_db):
    mock_session, mock_db_ops = mock_db
    chain = FilterChain()
    
    # Needs at least one filter passing
    chain.add_filter(MockFilter("f1"))
    
    with patch("filters.filter_chain.MessageContext") as MockContext:
        ctx_instance = MockContext.return_value
        ctx_instance.forwarded_messages = [123]
        ctx_instance.dup_signatures = [('sig1', 100)]
        ctx_instance.rule.target_chat.telegram_chat_id = 999
        
        await chain.process(None, None, None, None)
        
        mock_db_ops.add_media_signature.assert_awaited_with(mock_session, "999", 'sig1', 100)
