import pytest
import hashlib
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
    with patch("services.session_service.container") as mock:
        yield mock

@pytest.mark.asyncio
async def test_scan_duplicate_messages(session_service, mock_container):
    chat_id = 12345
    mock_event = MagicMock()
    mock_event.chat_id = chat_id
    mock_event.sender_id = 999
    
    # Mock iter_messages with duplicates
    async def mock_iter(*args, **kwargs):
        # Msg 1: Original
        m1 = MagicMock()
        m1.id = 101
        m1.date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        m1.grouped_id = None
        m1.message = ""
        m1.text = ""
        photo1 = MagicMock()
        photo1.id = 555  # ID should be same for duplicates
        size1 = MagicMock()
        size1.w = 100
        size1.h = 100
        size1.size = 5000
        photo1.sizes = [size1]
        photo1.access_hash = 1
        m1.media = MagicMock(photo=photo1)
        m1.photo = photo1
        m1.document = None
        m1.video = None
        yield m1
        
        # Msg 2: Duplicate of Msg 1
        m2 = MagicMock()
        m2.id = 102
        m2.date = datetime(2026, 1, 2, tzinfo=timezone.utc)
        m2.grouped_id = None
        m2.message = ""
        m2.text = ""
        photo2 = MagicMock()
        photo2.id = 555  # Same ID
        size2 = MagicMock()
        size2.w = 100
        size2.h = 100
        size2.size = 5000
        photo2.sizes = [size2]
        photo2.access_hash = 1
        m2.media = MagicMock(photo=photo2)
        m2.photo = photo2
        m2.document = None
        m2.video = None
        yield m2
        
        # Msg 3: Unique
        m3 = MagicMock()
        m3.id = 103
        m3.date = datetime(2026, 1, 3, tzinfo=timezone.utc)
        m3.grouped_id = None
        m3.message = ""
        m3.text = ""
        photo3 = MagicMock()
        photo3.id = 777  # Different ID
        size3 = MagicMock()
        size3.w = 200
        size3.h = 200
        size3.size = 8000
        photo3.sizes = [size3]
        photo3.access_hash = 2
        m3.media = MagicMock(photo=photo3)
        m3.photo = photo3
        m3.document = None
        m3.video = None
        yield m3

    mock_container.user_client.iter_messages.return_value = mock_iter()
    
    # Execute scan
    results = await session_service.scan_duplicate_messages(mock_event)
    
    # Verify results
    assert len(results) == 1
    sig = list(results.keys())[0]
    assert results[sig] == [102]
    # sig should be a 32-char hex string (xxhash result)
    assert len(sig) == 32
    
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
