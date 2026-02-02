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

@pytest.mark.asyncio
async def test_keyword_filter_smart_duplicate_call(keyword_filter, mock_context):
    mock_context.rule.target_chat = SimpleNamespace(telegram_chat_id="123456")
    mock_context.event.message = MagicMock()
    
    with patch("services.dedup.engine.smart_deduplicator.check_duplicate", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = (True, "reason")
        result = await keyword_filter._check_smart_duplicate(mock_context, mock_context.rule)
        assert result is True
        mock_check.assert_called_once()

@pytest.mark.asyncio
async def test_keyword_filter_delete_source_group(keyword_filter, mock_context):
    mock_context.event.message.grouped_id = 999
    with patch("services.media_service.media_service", new_callable=AsyncMock) as mock_media:
        mock_media.delete_media_group.return_value = True
        await keyword_filter._delete_source_message(mock_context)
        mock_media.delete_media_group.assert_called_once()

@pytest.mark.asyncio
async def test_keyword_filter_get_target_entity(keyword_filter, mock_context):
    mock_context.rule.target_chat = SimpleNamespace(telegram_chat_id="-100123")
    with patch("filters.keyword_filter.get_main_module", new_callable=AsyncMock) as mock_main:
        mock_main.return_value = SimpleNamespace(bot_client=MagicMock())
        with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = (None, -100123)
            entity = await keyword_filter._get_target_entity(mock_context.rule, 999)
            assert entity == -100123

@pytest.mark.asyncio
async def test_keyword_filter_schedule_deletion(keyword_filter, mock_context):
    mock_msg = MagicMock()
    with patch("services.task_service.message_task_manager", new_callable=AsyncMock) as mock_mgr:
        await keyword_filter._schedule_message_deletion(mock_msg, 5)
        mock_mgr.schedule_delete.assert_called_once_with(mock_msg, 5)

@pytest.mark.asyncio
async def test_keyword_filter_smart_dedup_full_rule(keyword_filter, mock_context):
    mock_context.rule.target_chat = SimpleNamespace(telegram_chat_id="123")
    mock_context.rule.enable_time_window_dedup = True
    mock_context.rule.dedup_time_window_hours = 12
    
    with patch("services.dedup.engine.smart_deduplicator", new_callable=AsyncMock) as mock_dedup:
        mock_dedup.check_duplicate.return_value = (False, "")
        mock_dedup.config = {}
        await keyword_filter._check_smart_duplicate(mock_context, mock_context.rule)
        call_args = mock_dedup.check_duplicate.call_args
        assert call_args[0][2]['time_window_hours'] == 12

@pytest.mark.asyncio
async def test_keyword_filter_delete_source_single(keyword_filter, mock_context):
    mock_context.event.client = AsyncMock()
    mock_context.event.message.grouped_id = None
    mock_context.event.message.id = 123
    
    with patch("filters.keyword_filter.get_main_module", new_callable=AsyncMock) as mock_get_main:
        mock_main = MagicMock()
        mock_main.user_client = AsyncMock()
        mock_get_main.return_value = mock_main
        
        mock_msg = AsyncMock()
        mock_main.user_client.get_messages.return_value = mock_msg
        
        await keyword_filter._delete_source_message(mock_context)
        mock_msg.delete.assert_called_once()

@pytest.mark.asyncio
async def test_keyword_filter_optimized_search_success(keyword_filter, mock_context):
    mock_context.rule.enable_search_optimization = True
    mock_context.rule.keywords = [SimpleNamespace(keyword="test")]
    mock_context.event.chat_id = 999
    
    with patch("filters.keyword_filter.get_main_module", new_callable=AsyncMock) as mock_main:
        mock_main.return_value = SimpleNamespace(user_client=AsyncMock())
        with patch("services.network.telegram_api_optimizer.api_optimizer.search_messages_by_keyword", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [MagicMock()] # Found something
            
            # RuleFilterService.check_keywords returns False to trigger optimized search
            with patch("services.rule.filter.RuleFilterService.check_keywords", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False
                result = await keyword_filter._process(mock_context)
                assert result is True
                mock_search.assert_called_once()

@pytest.mark.asyncio
async def test_keyword_filter_handle_dedup_deletion(keyword_filter, mock_context):
    mock_context.rule.allow_delete_source_on_dedup = True
    with patch.object(KeywordFilter, "_delete_source_message", new_callable=AsyncMock) as mock_del:
        with patch.object(KeywordFilter, "_send_dedup_notification", new_callable=AsyncMock) as mock_notify:
            await keyword_filter._handle_duplicate_message_deletion(mock_context, mock_context.rule)
            mock_del.assert_called_once()
            mock_notify.assert_called_once()

@pytest.mark.asyncio
async def test_keyword_filter_send_notification(keyword_filter, mock_context):
    with patch("filters.keyword_filter.get_main_module", new_callable=AsyncMock) as mock_main:
        mock_bot = AsyncMock()
        # Mock send_message to return an object with an ID (integer) to avoid serialization issues
        mock_msg = MagicMock()
        mock_msg.id = 123
        mock_msg.chat_id = 456
        mock_bot.send_message.return_value = mock_msg
        
        mock_main.return_value = SimpleNamespace(bot_client=mock_bot)
        with patch.object(KeywordFilter, "_get_target_entity", new_callable=AsyncMock) as mock_entity:
            mock_entity.return_value = 123456
            
            await keyword_filter._send_dedup_notification(mock_context, mock_context.rule)
            mock_bot.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_keyword_filter_enhanced_check_error(keyword_filter, mock_context):
    with patch("services.rule.filter.RuleFilterService.check_keywords", side_effect=Exception("oops")):
        # Should fallback to check_keywords again (and fail, or succeed if caught)
        # The code at line 94 does a fallback
        with patch("services.rule.filter.RuleFilterService.check_keywords", return_value=True) as mock_check:
            result = await keyword_filter._enhanced_keyword_check(mock_context.rule, "text", mock_context.event)
            assert result is True

@pytest.mark.asyncio
async def test_keyword_filter_delete_source_legacy_fallback(keyword_filter, mock_context):
    mock_context.event.client = AsyncMock()
    mock_context.event.message.grouped_id = 12345
    
    # Mock media_service as None to trigger fallback
    with patch("services.media_service.media_service", None):
        # Mock user_client.iter_messages
        mock_msg = MagicMock()
        mock_msg.grouped_id = 12345
        mock_msg.delete = AsyncMock()
        
        mock_client = AsyncMock()
        # Create an async iterator for iter_messages
        async def async_iter(*args, **kwargs):
            yield mock_msg
            
        mock_client.iter_messages = async_iter
        
        with patch("filters.keyword_filter.get_main_module", new_callable=AsyncMock) as mock_get_main:
            mock_main = MagicMock()
            mock_main.user_client = mock_client
            mock_get_main.return_value = mock_main
            
            await keyword_filter._delete_source_message(mock_context)
            mock_msg.delete.assert_called_once()

@pytest.mark.asyncio
async def test_keyword_filter_sender_regex_exception(keyword_filter, mock_context):
    mock_context.rule.required_sender_regex = "(" # Invalid regex
    # We need to ensure check_keywords returns True so we reach the sender check logic if it wasn't short-circuited
    # Actually wait, sender check is BEFORE keyword check.
    # KeywordFilter._process:
    # 1. dedup
    # 2. sender check
    # 3. keyword check
    
    # If regex raises exception, sender_ok becomes False (L58) or True (L60)?
    # L58: sender_ok = False.
    # So result should be False (should_forward = sender_ok and keyword_ok)
    
    with patch("services.rule.filter.RuleFilterService.check_keywords", return_value=True):
        # We need to rely on the actual re.search failure or mock it.
        # Passing invalid regex "(" to re.search raises re.error.
        result = await keyword_filter._process(mock_context)
        assert result is False

@pytest.mark.asyncio
async def test_keyword_filter_optimized_search_client_fail(keyword_filter, mock_context):
    mock_context.rule.enable_search_optimization = True
    
    with patch("services.rule.filter.RuleFilterService.check_keywords", return_value=False):
        with patch("filters.keyword_filter.get_main_module", side_effect=Exception("no client")):
            # Should catch exception and return basic_result (False)
            result = await keyword_filter._process(mock_context)
            assert result is False

