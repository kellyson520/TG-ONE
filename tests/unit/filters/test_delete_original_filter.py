import pytest
from unittest.mock import MagicMock
from filters.delete_original_filter import DeleteOriginalFilter
from types import SimpleNamespace

@pytest.fixture
def delete_original_filter():
    return DeleteOriginalFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.id = 1
    context.rule.is_delete_original = True
    context.event = MagicMock()
    context.event.message = MagicMock()
    context.event.message.id = 123
    context.event.message.grouped_id = None
    context.metadata = {}
    context.errors = []
    return context

@pytest.mark.asyncio
async def test_delete_original_filter_skip(delete_original_filter, mock_context):
    mock_context.rule.is_delete_original = False
    result = await delete_original_filter._process(mock_context)
    assert result is True
    assert 'delete_source_message' not in mock_context.metadata

@pytest.mark.asyncio
async def test_delete_original_filter_single(delete_original_filter, mock_context):
    result = await delete_original_filter._process(mock_context)
    assert result is True
    assert mock_context.metadata['delete_source_message'] is True
    assert 'delete_group_id' not in mock_context.metadata

@pytest.mark.asyncio
async def test_delete_original_filter_group(delete_original_filter, mock_context):
    mock_context.event.message.grouped_id = 999
    result = await delete_original_filter._process(mock_context)
    assert result is True
    assert mock_context.metadata['delete_source_message'] is True
    assert mock_context.metadata['delete_group_id'] == "999"
