"""
Bot Handler 单元测试 (bot_handler.py)
涵盖命令分发、管理员权限检查及回调入口
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Mock modules via a fixture to avoid global pollution
@pytest.fixture(autouse=True, scope="module")
def mock_modules():
    mocks = {
        'handlers.command_handlers': MagicMock(),
        'handlers.link_handlers': MagicMock(),
        'handlers.button.callback.callback_handlers': MagicMock(),
        'utils.core.constants': MagicMock(),
        'utils.media.media': MagicMock()
    }
    with patch.dict('sys.modules', mocks):
        yield mocks

# Now import module (moved inside tests if possible, but for now we'll keep at top but after mocks)
import handlers.bot_handler as bot_handler_mod
from handlers.bot_handler import handle_command

class TestBotHandler:

    @pytest.fixture(autouse=True)
    def inject_commands(self):
        """
        Manually inject command handlers into bot_handler module.
        Since 'from .command_handlers import *' from a MagicMock imports nothing,
        the names like 'handle_start_command' don't exist in bot_handler namespace.
        We must inject them for the lambdas to work.
        """
        bot_handler_mod.handle_start_command = AsyncMock()
        bot_handler_mod.handle_add_command = AsyncMock()
        bot_handler_mod.handle_settings_command = AsyncMock()
        yield

    @pytest.fixture
    def mock_deps(self):
        mock_client = MagicMock()
        mock_event = MagicMock()
        mock_event.message.text = "/start"
        mock_event.chat_id = 123
        mock_event.get_chat = AsyncMock() # Fix await event.get_chat()
        return mock_client, mock_event

    @pytest.mark.asyncio
    async def test_handle_command_not_admin(self, mock_deps):
        """测试非管理员忽略命令"""
        mock_client, mock_event = mock_deps
        
        with patch('handlers.bot_handler.is_admin', new_callable=AsyncMock) as mock_is_admin:
            mock_is_admin.return_value = False
            # Not admin returns early, before get_chat/get_user_id
            
            await handle_command(mock_client, mock_event)
            
            bot_handler_mod.handle_start_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_command_dispatch_start(self, mock_deps):
        """测试 /start 命令分发"""
        mock_client, mock_event = mock_deps
        mock_event.message.text = "/start"
        
        with patch('handlers.bot_handler.is_admin', new_callable=AsyncMock) as mock_is_admin, \
             patch('handlers.bot_handler.get_user_id', new_callable=AsyncMock) as mock_uid:
            
            mock_is_admin.return_value = True
            mock_uid.return_value = 123 # Different from chat_id implied? 
            # Logic: if not startswith / and chat==user (link check only).
            # Command check is separate.
            
            await handle_command(mock_client, mock_event)
            
            bot_handler_mod.handle_start_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_command_dispatch_with_args(self, mock_deps):
        """测试带参数命令 /add keyword"""
        mock_client, mock_event = mock_deps
        mock_event.message.text = "/add keyword"
        
        with patch('handlers.bot_handler.is_admin', new_callable=AsyncMock) as mock_is_admin, \
             patch('handlers.bot_handler.get_user_id', new_callable=AsyncMock) as mock_uid:
            
            mock_is_admin.return_value = True
            
            await handle_command(mock_client, mock_event)
            
            bot_handler_mod.handle_add_command.assert_called_once()
            args = bot_handler_mod.handle_add_command.call_args[0]
            assert args[1] == "add"
            assert args[2] == ["/add", "keyword"]

    @pytest.mark.asyncio
    async def test_handle_link_dispatch(self, mock_deps):
        """测试链接分发"""
        mock_client, mock_event = mock_deps
        mock_event.message.text = "https://t.me/c/123/456"
        
        # Mock dependencies
        mock_chat = MagicMock()
        mock_chat.id = 123
        mock_event.get_chat = AsyncMock(return_value=mock_chat)
        
        # Mock module-level function imports
        # handle_message_link IS imported explicitly so it exists as MagicMock (from sys.modules)
        # We can patch it to be AsyncMock
        
        with patch('handlers.bot_handler.is_admin', new_callable=AsyncMock) as mock_is_admin, \
             patch('handlers.bot_handler.get_user_id', new_callable=AsyncMock) as mock_get_uid, \
             patch('handlers.bot_handler.handle_message_link', new_callable=AsyncMock) as mock_handle_link:
             
            mock_is_admin.return_value = True
            mock_get_uid.return_value = 123
            
            await handle_command(mock_client, mock_event)
            
            mock_handle_link.assert_called_once()
