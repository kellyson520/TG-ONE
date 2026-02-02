import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.push_filter import PushFilter
from types import SimpleNamespace
import os

@pytest.fixture
def push_filter():
    return PushFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.id = 1
    context.rule.enable_push = True
    context.rule.enable_only_push = False
    context.rule.is_original_sender = True
    context.rule.is_original_time = True
    context.rule.is_original_link = True
    
    context.client = AsyncMock()
    context.event = MagicMock()
    context.event.chat_id = 987654
    context.event.message.id = 1
    context.event.message.media = None
    
    context.should_forward = True
    context.message_text = "test notification"
    context.sender_info = "From: user\n"
    context.time_info = "\nTime: now"
    context.original_link = "\nOriginal: link"
    context.media_files = []
    context.is_media_group = False
    context.media_group_messages = []
    context.skipped_media = []
    context.errors = []
    
    return context

@pytest.mark.asyncio
async def test_push_filter_skip_if_disabled(push_filter, mock_context):
    mock_context.rule.enable_push = False
    result = await push_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_push_filter_no_configs(push_filter, mock_context):
    mock_context.rule.enable_push = True
    
    # Mocking AsyncSessionManager
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = []
    
    with patch("filters.push_filter.AsyncSessionManager") as mock_manager:
        mock_manager.return_value.__aenter__.return_value = mock_session
        
        result = await push_filter._process(mock_context)
        assert result is True

@pytest.mark.asyncio
async def test_push_filter_text_notification(push_filter, mock_context):
    mock_context.rule.enable_push = True
    
    mock_config = SimpleNamespace()
    mock_config.push_channel = "tgram://bot_token/chat_id"
    mock_config.media_send_mode = "Single"
    
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_config]
    
    with patch("filters.push_filter.AsyncSessionManager") as mock_manager:
        mock_manager.return_value.__aenter__.return_value = mock_session
        
        with patch("apprise.Apprise") as mock_apprise:
            mock_ap_instance = mock_apprise.return_value
            mock_ap_instance.add.return_value = True
            mock_ap_instance.notify = MagicMock(return_value=True)
            
            result = await push_filter._process(mock_context)
            
            assert result is True
            mock_ap_instance.notify.assert_called_once()
            call_kwargs = mock_ap_instance.notify.call_args.kwargs
            assert "test notification" in call_kwargs["body"]

@pytest.mark.asyncio
async def test_push_filter_single_media(push_filter, mock_context):
    mock_context.media_files = ["temp/test.jpg"]
    
    mock_config = SimpleNamespace()
    mock_config.push_channel = "mailto://user:pass@example.com"
    mock_config.media_send_mode = "Single"
    
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_config]
    
    with patch("filters.push_filter.AsyncSessionManager") as mock_manager:
        mock_manager.return_value.__aenter__.return_value = mock_session
        with patch("apprise.Apprise") as mock_apprise:
            mock_ap_instance = mock_apprise.return_value
            mock_ap_instance.add.return_value = True
            mock_ap_instance.notify = MagicMock(return_value=True)
            
            with patch("os.path.exists", return_value=True):
                with patch("os.remove") as mock_remove:
                    result = await push_filter._process(mock_context)
                    
                    assert result is True
                    mock_ap_instance.notify.assert_called_once()
                    call_kwargs = mock_ap_instance.notify.call_args.kwargs
                    assert call_kwargs["attach"] == "temp/test.jpg"
                    # processed_files are cleared if it was not need_cleanup=True?
                    # wait, _push_single_media returns processed_files.
                    # if they came from context.media_files, push_filter._process clears them in finally block.
                    mock_remove.assert_called_once_with("temp/test.jpg")

@pytest.mark.asyncio
async def test_push_filter_media_group(push_filter, mock_context):
    mock_context.is_media_group = True
    mock_context.media_files = ["temp/img1.png", "temp/img2.png"]
    
    mock_config = SimpleNamespace()
    mock_config.push_channel = "pushed://user/token"
    mock_config.media_send_mode = "Multiple"
    
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_config]
    
    with patch("filters.push_filter.AsyncSessionManager") as mock_manager:
        mock_manager.return_value.__aenter__.return_value = mock_session
        with patch("apprise.Apprise") as mock_apprise:
            mock_ap_instance = mock_apprise.return_value
            mock_ap_instance.add.return_value = True
            mock_ap_instance.notify = MagicMock(return_value=True)
            
            with patch("os.path.exists", return_value=True):
                with patch("os.remove") as mock_remove:
                    result = await push_filter._process(mock_context)
                    
                    assert result is True
                    mock_ap_instance.notify.assert_called_once()
                    call_kwargs = mock_ap_instance.notify.call_args.kwargs
                    assert call_kwargs["attach"] == ["temp/img1.png", "temp/img2.png"]
                    assert mock_remove.call_count == 2
@pytest.mark.asyncio
async def test_push_filter_skipped_media_only(push_filter, mock_context):
    # Case where all media are skipped (size limit)
    mock_context.media_group_messages = []
    mock_context.skipped_media = [(MagicMock(), 50, "large.jpg")]
    
    mock_config = SimpleNamespace(push_channel="mock://", media_send_mode="Single")
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_config]
    
    with patch("filters.push_filter.AsyncSessionManager") as mock_manager:
        mock_manager.return_value.__aenter__.return_value = mock_session
        with patch("apprise.Apprise") as mock_apprise:
            mock_ap_instance = mock_apprise.return_value
            mock_ap_instance.add.return_value = True
            mock_ap_instance.notify = MagicMock(return_value=True)
            
            await push_filter._process(mock_context)
            
            call_kwargs = mock_ap_instance.notify.call_args.kwargs
            assert "超过大小限制" in call_kwargs["body"]

@pytest.mark.asyncio
async def test_push_filter_manual_download_and_cleanup(push_filter, mock_context):
    # Only push enabled, need to download manually
    mock_context.rule.enable_only_push = True
    msg = MagicMock()
    msg.media = True
    msg.download_media = AsyncMock(return_value="temp/manual.jpg")
    mock_context.event.message = msg
    
    mock_config = SimpleNamespace(push_channel="mock://", media_send_mode="Single")
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_config]
    
    with patch("filters.push_filter.AsyncSessionManager") as mock_manager:
        mock_manager.return_value.__aenter__.return_value = mock_session
        with patch("apprise.Apprise") as mock_apprise:
            mock_ap_instance = mock_apprise.return_value
            mock_ap_instance.add.return_value = True
            mock_ap_instance.notify = MagicMock(return_value=True)
            
            with patch("os.path.exists", return_value=True):
                with patch("os.remove") as mock_remove:
                    await push_filter._process(mock_context)
                    # Cleanup from push_single_media (need_cleanup branch)
                    assert mock_remove.call_count == 1

@pytest.mark.asyncio
async def test_push_filter_exception_returns_false(push_filter, mock_context):
    mock_session = MagicMock()
    mock_session.query.side_effect = Exception("db crash")
    
    with patch("filters.push_filter.AsyncSessionManager") as mock_manager:
        mock_manager.return_value.__aenter__.return_value = mock_session
        result = await push_filter._process(mock_context)
        assert result is False
        assert any("db crash" in e for e in mock_context.errors)
