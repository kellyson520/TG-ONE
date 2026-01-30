from unittest.mock import MagicMock, AsyncMock
import pytest
from unittest.mock import patch
from telethon import events
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
        event = AsyncMock(spec=events.NewMessage)
        
        # Setup reply to return a mock message that is JSON serializable
        mock_reply_msg = MagicMock()
        mock_reply_msg.id = 456
        mock_reply_msg.chat_id = -100111222333
        event.reply = AsyncMock(return_value=mock_reply_msg)
        
        event.delete = AsyncMock() # Manually add delete
        
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
        # We want to use REAL repositories for integration testing
        # Ensure container has real repos (which it should by default unless conftest mocked it)
        from repositories.rule_repo import RuleRepository
        from repositories.task_repo import TaskRepository
        
        # Ensure we have clean real repos linked to the test DB
        container.rule_repo = RuleRepository(container.db)
        container.task_repo = TaskRepository(container.db)
        container.user_client = AsyncMock()
        
        # Setup data in DB
        from models.models import Chat, ForwardRule
        async with container.db.session() as session:
            # Create Source/Target chats
            src_chat = Chat(telegram_chat_id="-100987654321", name="Test Group", type="channel")
            # Target chat must have current_add_id set to Source ID to establish context
            tgt_chat = Chat(telegram_chat_id="-100111222333", name="Target Group", type="channel", current_add_id="-100987654321")
            
            session.add(src_chat)
            session.add(tgt_chat)
            await session.commit()
            
            # Create Rule (Active)
            rule = ForwardRule(
                source_chat_id=src_chat.id,
                target_chat_id=tgt_chat.id,
                enable_rule=True
            )
            session.add(rule)
            await session.commit()

        # Now execute /add command
        # Note: handle_add_command will call RuleQueryService which uses container.rule_repo
        try:
            await handle_add_command(event, "add", ["/add", "test_keyword"])
        except Exception as e:
            import traceback
            pytest.fail(f"Handler raised exception: {e}\n{traceback.format_exc()}")
            
        # 3. Verify Database State
        async with container.db.session() as session:
            from models.models import Keyword
            from sqlalchemy import select
            stmt = select(Keyword).filter_by(keyword="test_keyword")
            result = await session.execute(stmt)
            keywords = result.scalars().all()
        
        assert len(keywords) > 0
        assert keywords[0].keyword == "test_keyword"
