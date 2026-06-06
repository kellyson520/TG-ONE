import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from services.session_service import SessionService

@pytest.fixture
def session_service():
    # Reset singleton
    SessionService._instance = None
    service = SessionService()
    service.user_sessions = {}
    return service

@pytest.fixture
def mock_container():
    # Patch the container in the module where SessionService logic resides
    with patch("services.session_service.container") as mock:
        # Mock DB Session
        mock_db_session = AsyncMock()
        mock.db.session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock Task Repo
        mock.task_repo.push = AsyncMock()
        mock.task_repo.get_queue_status = AsyncMock(return_value={'active_queues': 0})
        
        # Mock User Client
        mock.user_client.iter_messages = MagicMock()
        
        yield mock

@pytest.fixture
def mock_rule_mgmt():
    with patch("services.rule_management_service.rule_management_service") as mock:
        mock.get_rule_detail = AsyncMock(return_value={
            'success': True, 
            'source_chat': 'Test Source', 
            'target_chat': 'Test Target',
            'enabled': True
        })
        yield mock

@pytest.fixture
def mock_forward_settings():
    with patch("services.session_service.forward_settings_service") as mock:
        mock.get_global_media_settings = AsyncMock(return_value={})
        mock.update_global_media_setting = AsyncMock(return_value=True)
        yield mock

@pytest.mark.asyncio
async def test_session_service_singleton():
    s1 = SessionService()
    s2 = SessionService()
    assert s1 is s2

@pytest.mark.asyncio
async def test_time_range_ops(session_service):
    uid = 100
    session_service.set_time_range(uid, {'year': 2026})
    assert session_service.get_time_range(uid) == {'year': 2026}


@pytest.mark.asyncio
async def test_save_time_range_settings_compat(session_service):
    uid = 1001
    session_service.set_time_range(uid, {"start_year": 2026})

    assert await session_service.save_time_range_settings(uid) is True
    assert session_service.get_time_range(uid) == {"start_year": 2026}


@pytest.mark.asyncio
async def test_set_history_message_limit(session_service, mock_forward_settings):
    res = await session_service.set_history_message_limit(2500)

    assert res == {"success": True, "limit": 2500}
    mock_forward_settings.update_global_media_setting.assert_awaited_once_with(
        "HISTORY_MESSAGE_LIMIT", 2500
    )


@pytest.mark.asyncio
async def test_history_quick_time_range_helpers(session_service):
    uid = 101

    await session_service.set_days(uid, 7)
    tr = session_service.get_time_range(uid)
    assert tr["start_day"] == 7
    assert tr["start_year"] == 0
    assert tr["end_year"] == 0

    await session_service.set_year(uid, 2026)
    await session_service.set_month(uid, 13)
    await session_service.set_day_of_month(uid, 40)

    tr = session_service.get_time_range(uid)
    assert tr["start_year"] == 2026
    assert tr["start_month"] == 12
    assert tr["start_day"] == 31

@pytest.mark.asyncio
async def test_start_history_task_success(session_service, mock_container, mock_rule_mgmt, mock_forward_settings):
    user_id = 12345
    rule_id = 10
    
    # Setup state
    await session_service.set_selected_rule(user_id, rule_id)
    session_service.set_time_range(user_id, {})
    
    # Mock DB Query results
    mock_session = mock_container.db.session.return_value.__aenter__.return_value
    
    mock_chat = MagicMock()
    mock_chat.telegram_chat_id = 999
    
    # Rule
    mock_rule = MagicMock()
    mock_rule.id = rule_id
    mock_rule.source_chat_id = 1
    mock_rule.source_chat = MagicMock()
    mock_rule.source_chat.telegram_chat_id = 999
    mock_rule.target_chat = MagicMock()
    mock_rule.target_chat.telegram_chat_id = 888
    mock_container.rule_repo.get_by_id = AsyncMock(return_value=mock_rule)
    
    # Execute result - Scalar one or none
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
    res = await session_service.start_history_task(user_id)
    assert res['success'] is True, f"Start task failed: {res.get('error') or res.get('message')}"
    
    # Wait for completion explicitly
    stats = await session_service.get_history_progress(user_id)
    assert stats is not None, "Stats should not be None"
    if 'future' in stats:
        await stats['future']
    
    # Check status
    progress = await session_service.get_history_progress(user_id)
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
async def test_start_history_task_respects_message_limit(
    session_service,
    mock_container,
    mock_rule_mgmt,
    mock_forward_settings,
    monkeypatch,
):
    from core.config import settings

    user_id = 12345
    rule_id = 10
    monkeypatch.setattr(settings, "HISTORY_MESSAGE_LIMIT", 2)

    await session_service.set_selected_rule(user_id, rule_id)
    session_service.set_time_range(user_id, {})

    mock_session = mock_container.db.session.return_value.__aenter__.return_value
    mock_rule = MagicMock()
    mock_rule.id = rule_id
    mock_rule.source_chat_id = 1
    mock_rule.source_chat = MagicMock()
    mock_rule.source_chat.telegram_chat_id = 999
    mock_rule.target_chat = MagicMock()
    mock_rule.target_chat.telegram_chat_id = 888
    mock_container.rule_repo.get_by_id = AsyncMock(return_value=mock_rule)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_rule
    mock_session.execute.return_value = mock_result
    mock_session.get.return_value = MagicMock(telegram_chat_id=999)

    async def mock_iter(*args, **kwargs):
        for idx in range(5):
            msg = MagicMock()
            msg.id = idx + 1
            msg.date = datetime.now(timezone.utc)
            yield msg

    mock_container.user_client.iter_messages.return_value = mock_iter()

    res = await session_service.start_history_task(user_id)
    assert res["success"] is True

    progress = await session_service.get_history_progress(user_id)
    if "future" in progress:
        await progress["future"]

    progress = await session_service.get_history_progress(user_id)
    assert progress["done"] == 2
    assert mock_container.task_repo.push.await_count == 2

@pytest.mark.asyncio
async def test_backpressure_logic(session_service, mock_container, mock_rule_mgmt, mock_forward_settings):
    user_id = 111
    rule_id = 222
    await session_service.set_selected_rule(user_id, rule_id)
    
    # Mock DB
    mock_session = mock_container.db.session.return_value.__aenter__.return_value
    mock_result = MagicMock()
    mock_rule = MagicMock()
    mock_rule.source_chat_id = 1
    mock_rule.source_chat = MagicMock()
    mock_rule.source_chat.telegram_chat_id = 100
    mock_rule.target_chat.telegram_chat_id = 3
    mock_container.rule_repo.get_by_id = AsyncMock(return_value=mock_rule)
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
    mock_container.task_repo.get_queue_status.side_effect = [
        {'active_queues': 2000},
        {'active_queues': 0}
    ]
    
    # Start task with patched sleep
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await session_service.start_history_task(user_id)
        assert res['success'] is True, f"Start task failed: {res.get('error') or res.get('message')}"
        
        # Await future
        stats = await session_service.get_history_progress(user_id)
        assert stats is not None, "Stats should not be None"
        if 'future' in stats:
            await stats['future']
            
    # Now it must be finished
    progress = await session_service.get_history_progress(user_id)
    assert progress['status'] == 'completed', f"Task failed with error: {progress.get('error')}"
    assert progress['done'] == 150, f"Only processed {progress['done']} messages, expected 150"
    
    assert mock_container.task_repo.get_queue_status.call_count >= 1, f"Call count: {mock_container.task_repo.get_queue_status.call_count}"
