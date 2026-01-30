"""
Callback Handler 单元测试
测试回调处理器的分发与核心功能
"""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

# sys.modules mocks are now in conftest.py

class TestCallbackHandlers:
    """测试回调处理器基础分发与核心功能"""

    @pytest.fixture
    def mock_event(self):
        event = AsyncMock()
        event.data = b"settings:1"
        event.answer = AsyncMock()
        event.get_message = AsyncMock()
        event.edit = AsyncMock()
        event.get_chat.return_value = AsyncMock(id=123, name="Target Chat")
        event.delete = AsyncMock()
        return event

    async def test_handle_callback_new_menu(self, mock_event):
        """测试分发到新菜单系统"""
        with patch('handlers.button.callback.callback_handlers.callback_router') as mock_router:
            mock_handler = AsyncMock()
            mock_router.match.return_value = (mock_handler, {})
            
            from handlers.button.callback.callback_handlers import handle_callback
            mock_event.data = b"new_menu:test"
            await handle_callback(mock_event)
            
            mock_router.match.assert_called_with("new_menu:test")
            mock_handler.assert_called_once_with(mock_event)

    async def test_handle_callback_media(self, mock_event):
        """测试分发到媒体设置"""
        with patch('handlers.button.callback.callback_handlers.callback_router') as mock_router:
            mock_handler = AsyncMock()
            mock_router.match.return_value = (mock_handler, {})

            from handlers.button.callback.callback_handlers import handle_callback
            mock_event.data = b"media_settings:1"
            await handle_callback(mock_event)
            
            mock_router.match.assert_called_with("media_settings:1")
            mock_handler.assert_called_once_with(mock_event)

    async def test_callback_settings_success(self, mock_event):
        """测试显示规则列表 (callback_settings)"""
        with patch('core.container.container') as mock_container, \
             patch('core.helpers.id_utils.find_chat_by_telegram_id_variants') as mock_find_chat:
            
            from handlers.button.callback.modules.rule_settings import callback_settings
            
            mock_session = AsyncMock()
            mock_container.db_session.return_value.__aenter__.return_value = mock_session
            
            mock_chat_db = MagicMock()
            mock_chat_db.id = 123
            mock_find_chat.return_value = mock_chat_db
            
            mock_rule = MagicMock()
            mock_rule.id = 1
            mock_rule.source_chat.name = "SourceChat"
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_rule]
            mock_session.execute.return_value = mock_result
            
            mock_msg = AsyncMock()
            
            # Correct arguments: event, rule_id, session, message, data
            await callback_settings(mock_event, "settings", mock_session, mock_msg, "settings")
            
            mock_msg.edit.assert_called_once()
            assert "请选择要管理的转发规则" in mock_msg.edit.call_args[0][0]

    async def test_callback_rule_settings(self, mock_event):
        """测试显示单一规则设置 (callback_rule_settings)"""
        with patch('core.container.container') as mock_container, \
             patch('handlers.button.callback.modules.rule_settings.create_settings_text', new_callable=AsyncMock) as mock_text, \
             patch('handlers.button.callback.modules.rule_settings.create_buttons', new_callable=AsyncMock) as mock_buttons:
             
            from handlers.button.callback.modules.rule_settings import callback_rule_settings
            from models.models import ForwardRule
            
            mock_session = AsyncMock()
            mock_container.db_session.return_value.__aenter__.return_value = mock_session
            
            mock_rule = MagicMock(spec=ForwardRule, id=1)
            mock_session.get.return_value = mock_rule
            
            mock_text.return_value = "Settings Text"
            mock_buttons.return_value = []
            
            mock_msg = AsyncMock()
            
            # Correct arguments: event, rule_id, session, message, data
            await callback_rule_settings(mock_event, 1, mock_session, mock_msg, None)
            
            mock_msg.edit.assert_called_once()

    async def test_callback_delete(self, mock_event):
        """测试删除规则 (callback_delete)"""
        with patch('core.container.container') as mock_container, \
             patch('handlers.button.callback.modules.rule_actions.check_and_clean_chats', new_callable=AsyncMock) as mock_clean, \
             patch('handlers.button.callback.modules.rule_actions.respond_and_delete', new_callable=AsyncMock) as mock_respond, \
             patch('importlib.import_module', side_effect=ImportError("aiohttp not found")):
             
             mock_clean.return_value = 0
             
             from handlers.button.callback.modules.rule_actions import callback_delete
             from models.models import ForwardRule
             
             mock_session = AsyncMock()
             mock_container.db_session.return_value.__aenter__.return_value = mock_session
             
             mock_rule = MagicMock(spec=ForwardRule, id=1)
             mock_session.get.return_value = mock_rule
             
             mock_msg = AsyncMock()
             
             await callback_delete(mock_event, 1, mock_session, mock_msg, None)
             
             mock_session.delete.assert_called_with(mock_rule)
             mock_session.commit.assert_called()
    
    
    # Removed misplaced test_callback_dedup_scan_now from TestCallbackHandlers

class TestOtherCallback:
    """测试通用回调处理 (other_callback.py)"""

    @pytest.fixture
    def mock_event(self):
        event = AsyncMock()
        event.data = b"other_settings:1"
        event.answer = AsyncMock()
        event.get_message = AsyncMock()
        event.delete = AsyncMock()
        event.edit = AsyncMock()
        return event

    async def test_handle_other_callback_close(self, mock_event):
        """测试 close_settings 回调"""
        with patch('handlers.button.callback.other_callback.AsyncSessionManager') as mock_sm:
            from handlers.button.callback.other_callback import handle_other_callback
            mock_event.data = b"close_settings"
            await handle_other_callback(mock_event)
            mock_event.delete.assert_called_once()

    async def test_callback_dedup_scan_now(self, mock_event):
        """测试去重扫描 (callback_dedup_scan_now)"""
        with patch('handlers.button.callback.other_callback.AsyncSessionManager') as mock_sm, \
             patch('handlers.button.callback.other_callback.DBOperations') as mock_db_ops, \
             patch('core.helpers.common.get_main_module', new_callable=AsyncMock) as mock_get_mm:

            from handlers.button.callback.other_callback import callback_dedup_scan_now
            from models.models import ForwardRule
            
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__.return_value = mock_session
            
            mock_rule = MagicMock(spec=ForwardRule, id=1)
            mock_rule.source_chat.name = "Test Chat"
            mock_session.get.return_value = mock_rule
            
            mock_db_ops.create = AsyncMock()
            mock_db_instance = mock_db_ops.create.return_value
            mock_db_instance.scan_duplicate_media = AsyncMock(return_value=(['sig1'], {'sig1': 2}))
            
            mock_mm = MagicMock()
            mock_mm.user_client = AsyncMock()
            mock_get_mm.return_value = mock_mm
            
            mock_msg = AsyncMock()
            
            await callback_dedup_scan_now(mock_event, 1, mock_session, mock_msg, None)
            
            mock_db_instance.scan_duplicate_media.assert_called_once()
            mock_event.edit.assert_called()


class TestMediaCallback:
    """测试媒体设置回调 (media_callback.py)"""

    @pytest.fixture
    def mock_event(self):
        event = AsyncMock()
        event.data = b"media_settings:1"
        event.answer = AsyncMock()
        event.edit = AsyncMock()
        return event

    async def test_handle_media_callback_main(self, mock_event):
        """测试媒体设置主菜单显示"""
        with patch('handlers.button.callback.media_callback.AsyncSessionManager') as mock_session_manager, \
             patch('handlers.button.callback.media_callback.create_media_settings_buttons') as mock_buttons, \
             patch('handlers.button.callback.media_callback.get_media_settings_text') as mock_text:
            
            from handlers.button.callback.media_callback import handle_media_callback
            from models.models import ForwardRule
            from telethon import Button
            
            mock_event.data = b"media_settings:1"
            
            mock_session = AsyncMock()
            mock_session_manager.return_value.__aenter__.return_value = mock_session
            mock_session.get.return_value = MagicMock(spec=ForwardRule, id=1, max_media_size=100)
            
            mock_text.return_value = "Media Text"
            mock_buttons.return_value = [[Button.inline("Media")]]
            
            await handle_media_callback(mock_event)
            
            mock_event.edit.assert_called_once()


class TestAdminCallback:
    """测试管理员设置回调 (admin_callback.py)"""

    @pytest.fixture
    def mock_event(self):
        event = AsyncMock()
        event.data = b"admin_settings"
        event.answer = AsyncMock()
        event.edit = AsyncMock()
        event.sender_id = 12345
        event.get_message = AsyncMock()
        return event

    async def test_handle_admin_callback_forbidden(self, mock_event):
        """测试非管理员拒绝访问"""
        with patch('handlers.button.callback.admin_callback.AsyncSessionManager') as mock_session_manager, \
             patch('handlers.button.callback.admin_callback.is_admin', new_callable=AsyncMock) as mock_is_admin:
            
            mock_is_admin.return_value = False
            
            from handlers.button.callback.admin_callback import handle_admin_callback
            
            await handle_admin_callback(mock_event)
            mock_event.answer.assert_called_with("只有管理员可以访问管理面板", alert=True)

    async def test_handle_admin_callback_main(self, mock_event):
        """测试管理员访问主面板"""
        with patch('handlers.button.callback.admin_callback.AsyncSessionManager') as mock_session_manager, \
             patch('handlers.button.callback.admin_callback.is_admin', new_callable=AsyncMock) as mock_is_admin:
            
            mock_is_admin.return_value = True
            
            from handlers.button.callback.admin_callback import handle_admin_callback
            
            mock_event.data = b"admin_panel"
            
            mock_session = AsyncMock()
            mock_session_manager.return_value.__aenter__.return_value = mock_session
            
            await handle_admin_callback(mock_event)
            
            mock_event.edit.assert_called_once()
            assert "系统管理面板" in mock_event.edit.call_args[0][0]

    async def test_handle_admin_callback_db_health(self, mock_event):
        """测试数据库健康检查回调"""
        with patch('handlers.button.callback.admin_callback.AsyncSessionManager') as mock_session_manager, \
             patch('handlers.button.callback.admin_callback.is_admin', new_callable=AsyncMock) as mock_is_admin, \
             patch('handlers.button.callback.admin_callback.handle_db_health_command', new_callable=AsyncMock) as mock_handle_health:
            
            mock_is_admin.return_value = True
            
            from handlers.button.callback.admin_callback import handle_admin_callback
            
            mock_event.data = b"admin_db_health"
            
            mock_session = AsyncMock()
            mock_session_manager.return_value.__aenter__.return_value = mock_session
            
            await handle_admin_callback(mock_event)
            
            mock_handle_health.assert_called_once_with(mock_event)
            mock_event.answer.assert_called()

    async def test_handle_admin_callback_system_status(self, mock_event):
        """测试系统状态回调"""
        with patch('handlers.button.callback.admin_callback.AsyncSessionManager') as mock_session_manager, \
             patch('handlers.button.callback.admin_callback.is_admin', new_callable=AsyncMock) as mock_is_admin, \
             patch('handlers.button.callback.admin_callback.handle_system_status_command', new_callable=AsyncMock) as mock_handle_status:
            
            mock_is_admin.return_value = True
            
            from handlers.button.callback.admin_callback import handle_admin_callback
            
            mock_event.data = b"admin_system_status"
            
            mock_session = AsyncMock()
            mock_session_manager.return_value.__aenter__.return_value = mock_session
            
            await handle_admin_callback(mock_event)
            
            mock_handle_status.assert_called_once_with(mock_event)
            mock_event.answer.assert_called()

