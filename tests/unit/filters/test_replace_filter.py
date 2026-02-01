import pytest
from unittest.mock import MagicMock
from filters.replace_filter import ReplaceFilter
from types import SimpleNamespace

@pytest.fixture
def replace_filter():
    return ReplaceFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.id = 1
    context.rule.is_replace = True
    context.rule.replace_rules = []
    
    context.message_text = "original text with some pattern"
    context.metadata = {}
    context.errors = []
    return context

@pytest.mark.asyncio
async def test_replace_filter_skip_if_no_replace(replace_filter, mock_context):
    mock_context.rule.is_replace = False
    result = await replace_filter._process(mock_context)
    assert result is True
    assert mock_context.message_text == "original text with some pattern"

@pytest.mark.asyncio
async def test_replace_filter_no_rules(replace_filter, mock_context):
    mock_context.rule.replace_rules = []
    result = await replace_filter._process(mock_context)
    assert result is True
    assert mock_context.message_text == "original text with some pattern"

@pytest.mark.asyncio
async def test_replace_filter_full_replace(replace_filter, mock_context):
    rule1 = SimpleNamespace(pattern=".*", content="completely new text")
    mock_context.rule.replace_rules = [rule1]
    
    result = await replace_filter._process(mock_context)
    assert result is True
    assert mock_context.message_text == "completely new text"

@pytest.mark.asyncio
async def test_replace_filter_regex_replace(replace_filter, mock_context):
    rule1 = SimpleNamespace(pattern="original", content="modified")
    rule2 = SimpleNamespace(pattern="pattern", content="style")
    mock_context.rule.replace_rules = [rule1, rule2]
    
    result = await replace_filter._process(mock_context)
    assert result is True
    assert mock_context.message_text == "modified text with some style"
    assert mock_context.metadata['modified_text'] == "modified text with some style"

@pytest.mark.asyncio
async def test_replace_filter_invalid_regex(replace_filter, mock_context):
    rule1 = SimpleNamespace(pattern="[invalid", content="oops")
    mock_context.rule.replace_rules = [rule1]
    
    # regex error should be caught and logged, processing continues
    result = await replace_filter._process(mock_context)
    assert result is True
    assert mock_context.message_text == "original text with some pattern"
