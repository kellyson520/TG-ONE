import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from telethon import events
from models.models import ForwardRule
from core.container import container
from sqlalchemy import select

@pytest.mark.asyncio
class TestBotToDBPipeline:
    """
    True Integration Test: Simulates Bot Input -> Handler -> Service -> DB
    Uses the in-memory DB setup from conftest.py
    """
    
    @patch("handlers.bot_handler.is_admin", new_callable=AsyncMock)
    @patch("handlers.bot_handler.get_user_id", new_callable=AsyncMock)
    async def test_add_rule_pipeline(self, mock_get_user_id, mock_is_admin, db, clear_data):
        """Test adding a rule via bot command persists to Database."""
        from handlers.command_handlers import handle_add_command
        
        # 1. Setup Data
        mock_is_admin.return_value = True
        mock_get_user_id.return_value = 123456789
        
        # Mock Event
        from unittest.mock import MagicMock
        event = AsyncMock(spec=events.NewMessage)
        mock_msg = MagicMock()
        mock_msg.text = "/add test_keyword"
        mock_msg.id = 123
        # Use TARGET chat ID for the event where command is typed
        target_chat_id_val = -100111222333 
        mock_msg.chat_id = target_chat_id_val
        event.message = mock_msg
        
        event.chat_id = target_chat_id_val
        event.sender_id = 123456789
        event.sender = MagicMock()
        event.sender.id = 123456789
        
        # Mock Chat object returned by get_chat()
        chat_mock = MagicMock()
        chat_mock.id = target_chat_id_val
        chat_mock.title = "Target Group"
        chat_mock.username = "targetgroup"
        event.get_chat = AsyncMock(return_value=chat_mock)
        
        # 2. Execute Handler (Pipeline trigger)
        container.user_client = AsyncMock()
        
        from services.rule_management_service import rule_management_service
        
        # Manually create a rule in DB as setup
        from models.models import ForwardRule, Chat
        
        async with container.db.session() as session:
            # Create Source/Target chats
            src_chat = Chat(telegram_chat_id="-100987654321", name="Test Group", chat_type="channel")
            # Target chat must have current_add_id set to Source ID to establish context
            tgt_chat = Chat(telegram_chat_id="-100111222333", name="Target Group", chat_type="channel", current_add_id="-100987654321")
            
            session.add(src_chat)
            session.add(tgt_chat)
            await session.commit()
            
            # Refresh to get IDs
            # (In async session, refresh might be needed if we need IDs immediately, 
            # but here we can just query or rely on flush)
            # Actually, let's just create the rule with the objects directly if flush happened, or query ids.
            # But safer to use variables after flush.
            
            # Create Rule (Active)
            rule = ForwardRule(
                source_chat_id=src_chat.id,
                target_chat_id=tgt_chat.id,
                enable_rule=True
            )
            session.add(rule)
            await session.commit()

        # Now execute /add command
        try:
            # handle_add_command(event, command, parts)
            await handle_add_command(event, "add", ["/add", "test_keyword"])
        except Exception as e:
            pytest.fail(f"Handler raised exception: {e}")
            
        # 3. Verify Database State
        # Check if Keyword was added to the Rule
        # 3. Verify Database State
        # Check if Keyword was added to the Rule
        async with container.db.session() as session:
            # We need to find the rule again
            from models.models import Keyword
            stmt = select(Keyword).filter_by(keyword="test_keyword")
            result = await session.execute(stmt)
            keywords = result.scalars().all()
        
        assert len(keywords) > 0
        assert keywords[0].keyword == "test_keyword"
