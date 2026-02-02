import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.rss_filter import RSSFilter
from types import SimpleNamespace

@pytest.fixture
def rss_filter():
    return RSSFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.client = AsyncMock()
    context.event = MagicMock()
    context.rule = SimpleNamespace()
    context.rule.id = 1
    context.rule.only_rss = False
    context.should_forward = True
    context.is_media_group = False
    return context

@pytest.mark.asyncio
async def test_rss_filter_skip_if_disabled(rss_filter, mock_context):
    with patch("filters.rss_filter.RSS_ENABLED", False):
        result = await rss_filter._process(mock_context)
        assert result is True

@pytest.mark.asyncio
async def test_rss_filter_skip_if_not_forward(rss_filter, mock_context):
    mock_context.should_forward = False
    with patch("filters.rss_filter.RSS_ENABLED", True):
        result = await rss_filter._process(mock_context)
        assert result is False

@pytest.mark.asyncio
async def test_rss_filter_single_item(rss_filter, mock_context):
    with patch("filters.rss_filter.RSS_ENABLED", True):
        with patch("services.rss_service.rss_service", new_callable=AsyncMock) as mock_service:
            result = await rss_filter._process(mock_context)
            assert result is True
            mock_service.process_rss_item.assert_called_once()

@pytest.mark.asyncio
async def test_rss_filter_media_group(rss_filter, mock_context):
    mock_context.is_media_group = True
    mock_context.media_group_messages = [MagicMock(), MagicMock()]
    
    with patch("filters.rss_filter.RSS_ENABLED", True):
        with patch("services.rss_service.rss_service", new_callable=AsyncMock) as mock_service:
            result = await rss_filter._process(mock_context)
            assert result is True
            mock_service.process_media_group_rss.assert_called_once()

@pytest.mark.asyncio
async def test_rss_filter_only_rss(rss_filter, mock_context):
    mock_context.rule.only_rss = True
    with patch("filters.rss_filter.RSS_ENABLED", True):
        with patch("services.rss_service.rss_service", new_callable=AsyncMock) as mock_service:
            result = await rss_filter._process(mock_context)
            assert result is False  # Stops the chain
            mock_service.process_rss_item.assert_called_once()

@pytest.mark.asyncio
async def test_rss_filter_exception(rss_filter, mock_context):
    with patch("filters.rss_filter.RSS_ENABLED", True):
        with patch("services.rss_service.rss_service", new_callable=AsyncMock) as mock_service:
            mock_service.process_rss_item.side_effect = Exception("error")
            result = await rss_filter._process(mock_context)
            assert result is True  # Doesn't block by default
