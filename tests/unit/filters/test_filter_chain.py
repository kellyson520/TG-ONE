import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from filters.filter_chain import FilterChain, FilterNode, ParallelNode
from filters.base_filter import BaseFilter
from filters.context import MessageContext

class MockFilter(BaseFilter):
    def __init__(self, name, should_continue=True, delay=0, error=None):
        super().__init__(name=name)
        self.should_continue = should_continue
        self.delay = delay
        self.error = error
        
    async def _process(self, context: MessageContext) -> bool:
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.should_continue

@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=MessageContext)
    ctx.errors = []
    ctx.trace_id = "test-trace"
    return ctx

@pytest.mark.asyncio
async def test_filter_node_execution(mock_context):
    f = MockFilter("f1", should_continue=True)
    node = FilterNode(f)
    res = await node.execute(mock_context)
    assert res is True
    
    f2 = MockFilter("f2", should_continue=False)
    node2 = FilterNode(f2)
    res2 = await node2.execute(mock_context)
    assert res2 is False

@pytest.mark.asyncio
async def test_parallel_node_execution(mock_context):
    f1 = MockFilter("f1", should_continue=True)
    f2 = MockFilter("f2", should_continue=True)
    node = ParallelNode([FilterNode(f1), FilterNode(f2)])
    
    res = await node.execute(mock_context)
    assert res is True
    
    f3 = MockFilter("f3", should_continue=False)
    node2 = ParallelNode([FilterNode(f1), FilterNode(f3)])
    res2 = await node2.execute(mock_context)
    assert res2 is False

@pytest.mark.asyncio
async def test_filter_chain_sequential(mock_context):
    chain = FilterChain()
    chain.add_filter(MockFilter("f1", should_continue=True))
    chain.add_filter(MockFilter("f2", should_continue=True))
    
    res = await chain.process_context(mock_context)
    assert res is True
    assert len(chain.nodes) == 2

@pytest.mark.asyncio
async def test_filter_chain_interruption(mock_context):
    chain = FilterChain()
    chain.add_filter(MockFilter("f1", should_continue=False))
    
    f2 = MockFilter("f2")
    f2.process = AsyncMock()
    chain.add_filter(f2)
    
    res = await chain.process_context(mock_context)
    assert res is False
    f2.process.assert_not_called()

@pytest.mark.asyncio
async def test_filter_chain_with_parallel_group(mock_context):
    chain = FilterChain()
    chain.add_filter(MockFilter("f1"))
    chain.add_parallel_group([MockFilter("p1"), MockFilter("p2")])
    
    assert len(chain.nodes) == 2
    assert isinstance(chain.nodes[1], ParallelNode)
    
    res = await chain.process_context(mock_context)
    assert res is True

@pytest.mark.asyncio
async def test_filter_node_timeout(mock_context):
    f = MockFilter("timeout", delay=0.1)
    node = FilterNode(f)
    # Patch asyncio.wait_for timeout
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        res = await node.execute(mock_context)
        assert res is False
        assert any("执行超时" in e for e in mock_context.errors)

@pytest.mark.asyncio
async def test_filter_node_exception(mock_context):
    f = MockFilter("error", error=ValueError("oops"))
    node = FilterNode(f)
    # Note: BaseFilter.process has @handle_errors(default_return=False),
    # so exceptions in _process are caught and False is returned.
    res = await node.execute(mock_context)
    assert res is False

@pytest.mark.asyncio
async def test_parallel_node_mixed_failure(mock_context):
    f1 = MockFilter("ok")
    f2 = MockFilter("fail", should_continue=False)
    node = ParallelNode([FilterNode(f1), FilterNode(f2)])
    res = await node.execute(mock_context)
    assert res is False

@pytest.mark.asyncio
async def test_parallel_node_exception(mock_context):
    # This specifically tests the branch where gather returns an Exception as a result
    f1 = FilterNode(MockFilter("f1"))
    # Mocking execute directly to return an Exception
    f2 = MagicMock(spec=FilterNode)
    f2.execute = AsyncMock(side_effect=Exception("parallel error"))
    
    node = ParallelNode([f1, f2])
    res = await node.execute(mock_context)
    assert res is False
    # If it's a parallel exception caught by FilterNode.execute
    # assert any("parallel error" in e for e in mock_context.errors)

@pytest.mark.asyncio
async def test_filter_chain_legacy_process(mock_context):
    chain = FilterChain()
    chain.add_filter(MockFilter("f1"))
    
    # Mock MessageContext constructor
    with patch("filters.filter_chain.MessageContext") as mock_ctx_cls:
        mock_ctx_cls.return_value = mock_context
        # Use MagicMock for others
        res = await chain.process(MagicMock(), MagicMock(), 123, MagicMock())
        assert res is True
