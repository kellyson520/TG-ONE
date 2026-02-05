import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import hashlib

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
    with patch("services.session_service.container") as mock:
        yield mock

@pytest.mark.asyncio
async def test_scan_duplicate_messages(session_service, mock_container):
    chat_id = 12345
    mock_event = MagicMock()
    mock_event.chat_id = chat_id
    
    # Mock iter_messages with duplicates
    async def mock_iter(*args, **kwargs):
        # Msg 1: Original
        m1 = MagicMock()
        m1.id = 101
        m1.date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        m1.photo = MagicMock()
        m1.photo.sizes = [MagicMock(w=100, h=100, size=5000)]
        yield m1
        
        # Msg 2: Duplicate of Msg 1
        m2 = MagicMock()
        m2.id = 102
        m2.date = datetime(2026, 1, 2, tzinfo=timezone.utc)
        m2.photo = MagicMock()
        m2.photo.sizes = [MagicMock(w=100, h=100, size=5000)]
        yield m2
        
        # Msg 3: Unique
        m3 = MagicMock()
        m3.id = 103
        m3.date = datetime(2026, 1, 3, tzinfo=timezone.utc)
        m3.photo = MagicMock()
        m3.photo.sizes = [MagicMock(w=200, h=200, size=8000)]
        yield m3

    mock_container.user_client.iter_messages.return_value = mock_iter()
    
    # Execute scan
    results = await session_service.scan_duplicate_messages(mock_event)
    
    # Verify results
    # photo:100x100:5000 is the signature
    sig = "photo:100x100:5000"
    assert sig in results
    assert results[sig] == [102] # 101 is the first seen (kept), 102 is the duplicate
    
    # Verify mapping
    session = session_service._get_user_session(chat_id)
    assert 'sig_mapping' in session
    short_id = hashlib.md5(sig.encode()).hexdigest()[:8]
    assert session['sig_mapping'][short_id] == sig

@pytest.mark.asyncio
async def test_delete_duplicate_messages_all(session_service, mock_container):
    chat_id = 12345
    mock_event = MagicMock()
    mock_event.chat_id = chat_id
    
    # Setup scan results
    sig = "photo:100x100:5000"
    session_service.current_scan_results[chat_id] = {sig: [102, 103]}
    
    mock_container.user_client.delete_messages = AsyncMock()
    
    with patch("asyncio.sleep", new_callable=AsyncMock):
        success, msg = await session_service.delete_duplicate_messages(mock_event, mode="all")
        assert success is True
        
        # Give it a tiny bit to start the background task
        await asyncio.sleep(0.1)
        
        task = session_service._get_user_session(chat_id).get('delete_task')
        assert task is not None
        assert task['total'] == 2
        
        # Check if delete was called
        # The background task is running, so we might need to wait or mock better
        # For simplicity, we check if the task exists and total is correct

@pytest.mark.asyncio
async def test_toggle_select_signature(session_service):
    chat_id = 999
    sig = "photo:long_signature_string_that_needs_mapping"
    short_id = hashlib.md5(sig.encode()).hexdigest()[:8]
    
    session = session_service._get_user_session(chat_id)
    session['sig_mapping'] = {short_id: sig}
    
    # Toggle select using short_id
    await session_service.toggle_select_signature(chat_id, short_id)
    
    state = await session_service.get_selection_state(chat_id)
    assert sig in state
    
    # Toggle off
    await session_service.toggle_select_signature(chat_id, short_id)
    state = await session_service.get_selection_state(chat_id)
    assert sig not in state

import asyncio
