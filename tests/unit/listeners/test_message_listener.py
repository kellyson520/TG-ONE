import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.container import container
from listeners.message_listener import setup_listeners

@pytest.fixture
def mock_clients():
    user_client = MagicMock()
    bot_client = MagicMock()
    
    # Mock bot_client.get_me
    bot_me = MagicMock()
    bot_me.id = 123456
    bot_client.get_me = AsyncMock(return_value=bot_me)
    
    # Mock user_client.on decorator
    def on_decorator(event_type):
        def decorator(func):
            user_client.listener_func = func # Capture the listener
            return func
        return decorator
    user_client.on = on_decorator
    
    return user_client, bot_client

@pytest.fixture
def mock_task_repo():
    container.task_repo = AsyncMock()
    return container.task_repo

@pytest.fixture
def mock_session_manager():
    with patch('handlers.button.session_management.session_manager') as mock:
        mock.user_sessions = {}
        yield mock

@pytest.mark.asyncio
async def test_user_message_listener_normal_flow(mock_clients, mock_task_repo, mock_session_manager):
    user_client, bot_client = mock_clients
    
    # Setup listeners to capture the internal user_message_listener
    await setup_listeners(user_client, bot_client)
    listener = user_client.listener_func
    
    # Create a mock event
    event = MagicMock()
    event.sender_id = 999
    event.chat_id = 888
    event.id = 1001
    event.message.media = None
    event.message.grouped_id = None
    event.text = "Hello"
    
    # Execute listener
    await listener(event)
    
    # Verify task_repo push
    mock_task_repo.push.assert_called_once()
    args = mock_task_repo.push.call_args
    assert args[0][0] == "process_message"
    payload = args[0][1]
    assert payload["chat_id"] == 888
    assert payload["message_id"] == 1001
    assert payload["has_media"] is False

@pytest.mark.asyncio
async def test_user_message_listener_manual_download(mock_clients, mock_task_repo, mock_session_manager):
    user_client, bot_client = mock_clients
    await setup_listeners(user_client, bot_client)
    listener = user_client.listener_func
    
    # Setup session state
    chat_id = 777
    user_id = 999
    mock_session_manager.user_sessions = {
        user_id: {
            chat_id: {
                'state': 'waiting_for_file',
                'target_chat_id': 666
            }
        }
    }
    
    # Create mock event with media
    event = MagicMock()
    event.sender_id = user_id
    event.chat_id = chat_id
    event.id = 2002
    event.message.media = True # Has media
    event.respond = AsyncMock()
    
    # Execute
    await listener(event)
    
    # Verify task_repo push to manual_download
    mock_task_repo.push.assert_called_once()
    args = mock_task_repo.push.call_args
    assert args[0][0] == "manual_download"
    assert args[1]["priority"] == 100
    
    payload = args[0][1]
    assert payload["manual_trigger"] is True
    assert payload["target_chat_id"] == 666
    
    # Verify response and session cleared
    event.respond.assert_called_with("✅ 已加入下载队列。")
    # Note: Since we mocked the session_manager instance, we need to check if we can modify the dict.
    # But wait, looking at the code: `user_session = session_manager.user_sessions.get(...)`
    # It modifies the dict from `get`.
    # Let's verify the dict modification if possible, or just the logic flow.
    # The actual code calls:
    # if event.chat_id in user_session: user_session.pop(event.chat_id)
    # Since `user_session` is a ref to the inner dict of `mock_session_manager.user_sessions`,
    # popping from it should reflect.
    
    # However, `session_manager.user_sessions.get(user_id, {})` returns a dict.
    # Then `user_session` is that dict.
    # Then `user_session.pop` is called.
    # So checking `mock_session_manager.user_sessions[user_id]` should show it empty or missing key.
    assert chat_id not in mock_session_manager.user_sessions[user_id]

@pytest.mark.asyncio
async def test_user_message_listener_manual_download_invalid_input(mock_clients, mock_task_repo, mock_session_manager):
    user_client, bot_client = mock_clients
    await setup_listeners(user_client, bot_client)
    listener = user_client.listener_func
    
    # Setup session state
    chat_id = 777
    user_id = 999
    mock_session_manager.user_sessions = {
        user_id: {
            chat_id: {'state': 'waiting_for_file'}
        }
    }
    
    # Create mock event WITHOUT media
    event = MagicMock()
    event.sender_id = user_id
    event.chat_id = chat_id
    event.message.media = None
    event.text = "Just text"
    event.respond = AsyncMock()
    
    # Execute
    await listener(event)
    
    # Verify NO task push
    mock_task_repo.push.assert_not_called()
    
    # Verify warning response
    event.respond.assert_called_with("⚠️ 请发送文件。")
