
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from handlers.button.session_management import SessionManager

@pytest.fixture
def session_manager():
    # Reset singleton
    SessionManager._instance = None
    manager = SessionManager()
    manager.user_sessions = {}
    return manager

@pytest.fixture
def mock_container():
    # Patch the container in the module where SessionManager logic resides
    with patch("handlers.button.session_management.container") as mock:
        # Mock DB Session
        mock_db_session = AsyncMock()
        mock.db.session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock Task Repo
        mock.task_repo.push = AsyncMock()
        mock.task_repo.get_queue_status = AsyncMock(return_value={'active_queues': 0})
        
        # Mock User Client
        mock.user_client.iter_messages = MagicMock()
        
        yield mock

@pytest.mark.asyncio
async def test_session_manager_singleton():
    m1 = SessionManager()
    m2 = SessionManager()
    assert m1 is m2

@pytest.mark.asyncio
async def test_time_range_ops(session_manager):
    uid = 100
    session_manager.set_time_range(uid, {'year': 2026})
    assert session_manager.get_time_range(uid) == {'year': 2026}

@pytest.mark.asyncio
async def test_start_history_task_success(session_manager, mock_container):
    user_id = 12345
    rule_id = 10
    
    # Setup state
    await session_manager.set_selected_rule(user_id, rule_id)
    session_manager.set_time_range(user_id, {})
    
    # Mock DB Query results
    mock_session = mock_container.db.session.return_value.__aenter__.return_value
    
    mock_chat = MagicMock()
    mock_chat.telegram_chat_id = 999
    
    # Rule
    mock_rule = MagicMock()
    mock_rule.id = rule_id
    mock_rule.source_chat_id = 1
    mock_rule.target_chat = MagicMock()
    mock_rule.target_chat.telegram_chat_id = 888
    
    # Execute result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_rule
    mock_session.execute.return_value = mock_result
    
    mock_session.get.return_value = mock_chat

    # Mock iter_messages (Async Generator)
    async def mock_iter(*args, **kwargs):
        msg = MagicMock()
        msg.id = 500
        msg.date = datetime.now(timezone.utc)
        yield msg
    
    mock_container.user_client.iter_messages.return_value = mock_iter()

    # Start
    res = await session_manager.start_history_task(user_id)
    assert res['success'] is True
    
    # Wait for completion explicitly
    stats = await session_manager.get_history_progress(user_id)
    if 'future' in stats:
        await stats['future']
    
    # Check status
    progress = await session_manager.get_history_progress(user_id)
    assert progress['status'] == 'completed'
    assert progress['total'] == 0
    assert progress['done'] == 1
    
    # Check push called
    mock_container.task_repo.push.assert_called_once()
    args, kwargs = mock_container.task_repo.push.call_args
    # "process_message" is args[0], payload is args[1]
    payload = args[1] if len(args) > 1 else kwargs['payload']
    assert payload['chat_id'] == 999
    assert payload['target_chat_id'] == 888

@pytest.mark.asyncio
async def test_backpressure_logic(session_manager, mock_container):
    user_id = 111
    rule_id = 222
    await session_manager.set_selected_rule(user_id, rule_id)
    
    # Mock DB
    mock_session = mock_container.db.session.return_value.__aenter__.return_value
    mock_result = MagicMock()
    mock_rule = MagicMock()
    mock_rule.source_chat_id = 1
    mock_rule.target_chat.telegram_chat_id = 3
    mock_result.scalar_one_or_none.return_value = mock_rule
    mock_session.execute.return_value = mock_result
    mock_session.get.return_value = MagicMock(telegram_chat_id=100)

    # Produce 150 messages (trigger backpressure check at 100)
    async def mock_iter(*args, **kwargs):
        for i in range(150):
            msg = MagicMock()
            msg.id = i
            msg.date = datetime.now(timezone.utc)
            yield msg
            
    mock_container.user_client.iter_messages.return_value = mock_iter()
    
    # Set queue status high to trigger warning
    # 1. First call (count 100): 2000 -> pause -> wait
    # 2. Second call (re-check): 0 -> resume
    mock_container.task_repo.get_queue_status.side_effect = [
        {'active_queues': 2000},
        {'active_queues': 0}
    ]
    
    # Start task with patched sleep
    # We patch Sleep to be instant
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await session_manager.start_history_task(user_id)
        
        # Await future
        stats = await session_manager.get_history_progress(user_id)
        if 'future' in stats:
            await stats['future']
            
    # Now it must be finished
    progress = await session_manager.get_history_progress(user_id)
    assert progress['status'] == 'completed', f"Task failed with error: {progress.get('error')}"
    assert progress['done'] == 150, f"Only processed {progress['done']} messages, expected 150"
    
    assert mock_container.task_repo.get_queue_status.call_count >= 2, f"Call count: {mock_container.task_repo.get_queue_status.call_count}"
    
