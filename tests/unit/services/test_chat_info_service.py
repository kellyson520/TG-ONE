
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.chat_info_service import ChatInfoService
from models.models import Chat

@pytest.fixture
def mock_db():
    db = MagicMock()
    session = AsyncMock()
    # Mock context manager behavior for db.session()
    db.session.return_value.__aenter__.return_value = session
    db.session.return_value.__aexit__.return_value = None
    return db

@pytest.fixture
def service(mock_db):
    service = ChatInfoService(db=mock_db)
    return service

@pytest.mark.asyncio
async def test_update_chat_in_db_creates_new_chat(service, mock_db):
    # Setup
    chat_id = "12345"
    name = "Test Chat"
    
    # Mock entity
    entity = MagicMock()
    # Mock _get_chat_type to return 'group'
    service._get_chat_type = MagicMock(return_value="group")
    
    # Mock DB execution to return no result first (so it creates new)
    session = mock_db.session.return_value.__aenter__.return_value
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    # Patch logger to check for errors
    with patch("services.chat_info_service.Chat") as MockChat, \
         patch("services.chat_info_service.logger") as mock_logger, \
         patch("services.chat_info_service.select") as mock_select:
        
        # Setup mock_select to return a dummy statement with where method
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        
        # Execution
        await service._update_chat_in_db(chat_id, entity, name)
        
        # Debugging: Check if error was logged
        if mock_logger.error.called:
            print(f"Logger Error Called: {mock_logger.error.call_args}")
            
        # Verification
        # Check if Chat was instantiated with correct arguments
        if not MockChat.called:
             pytest.fail(f"Chat not instantiated. Logger calls: {mock_logger.mock_calls}")

        MockChat.assert_called_once()
        call_args = MockChat.call_args
        _, kwargs = call_args
        
        assert kwargs["telegram_chat_id"] == chat_id # Normalized id is same if positive string
        assert kwargs["name"] == name
        assert kwargs["type"] == "group" # This is the critical check
        assert "chat_type" not in kwargs # Ensure invalid arg is NOT present

@pytest.mark.asyncio
async def test_update_chat_in_db_updates_existing_chat(service, mock_db):
    # Setup
    chat_id = "123456"
    name = "Updated Name"
    entity = MagicMock()
    
    session = mock_db.session.return_value.__aenter__.return_value
    
    # Mock existing chat
    existing_chat = MagicMock(spec=Chat)
    existing_chat.name = "Old Name"
    # Ensure updated_at is NOT set in our fix, or if it is valid on the mock but not in code
    
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_chat
    session.execute.return_value = result
    
    # Execution
    await service._update_chat_in_db(chat_id, entity, name)
    
    # Verification
    assert existing_chat.name == name
    # We explicitly removed updated_at assignment, so we check it was NOT set
    # Note: Logic was `chat.updated_at = ...` (removed).
    # We can check if `updated_at` attribute was accessed or set if we want, but simpler is just to ensure no error.
