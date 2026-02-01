import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.keyword_filter import KeywordFilter
from types import SimpleNamespace

@pytest.fixture
def keyword_filter():
    return KeywordFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.id = 1
    context.rule.enable_dedup = False
    context.rule.required_sender_id = None
    context.rule.required_sender_regex = None
    context.rule.enable_search_optimization = False
    
    context.message_text = "hello world"
    context.event = MagicMock()
    context.sender_id = 123
    context.sender_name = "John Doe"
    context.should_forward = True
    return context

@pytest.mark.asyncio
async def test_keyword_filter_success(keyword_filter, mock_context):
    with patch("services.rule.filter.RuleFilterService.check_keywords", return_value=True):
        result = await keyword_filter._process(mock_context)
        assert result is True

@pytest.mark.asyncio
async def test_keyword_filter_fail(keyword_filter, mock_context):
    with patch("services.rule.filter.RuleFilterService.check_keywords", return_value=False):
        result = await keyword_filter._process(mock_context)
        assert result is False

@pytest.mark.asyncio
async def test_keyword_filter_sender_match_id(keyword_filter, mock_context):
    mock_context.rule.required_sender_id = "123"
    with patch("services.rule.filter.RuleFilterService.check_keywords", return_value=True):
        result = await keyword_filter._process(mock_context)
        assert result is True

@pytest.mark.asyncio
async def test_keyword_filter_sender_mismatch_id(keyword_filter, mock_context):
    mock_context.rule.required_sender_id = "456"
    with patch("services.rule.filter.RuleFilterService.check_keywords", return_value=True):
        result = await keyword_filter._process(mock_context)
        assert result is False

@pytest.mark.asyncio
async def test_keyword_filter_sender_regex_match(keyword_filter, mock_context):
    mock_context.rule.required_sender_regex = "John.*"
    with patch("services.rule.filter.RuleFilterService.check_keywords", return_value=True):
        result = await keyword_filter._process(mock_context)
        assert result is True

@pytest.mark.asyncio
async def test_keyword_filter_sender_regex_mismatch(keyword_filter, mock_context):
    mock_context.rule.required_sender_regex = "^Alice"
    with patch("services.rule.filter.RuleFilterService.check_keywords", return_value=True):
        result = await keyword_filter._process(mock_context)
        assert result is False

@pytest.mark.asyncio
async def test_keyword_filter_dedup(keyword_filter, mock_context):
    mock_context.rule.enable_dedup = True
    
    with patch.object(KeywordFilter, "_check_smart_duplicate", return_value=True):
        with patch.object(KeywordFilter, "_handle_duplicate_message_deletion", return_value=None):
            result = await keyword_filter._process(mock_context)
            assert result is False
            assert mock_context.should_forward is False
