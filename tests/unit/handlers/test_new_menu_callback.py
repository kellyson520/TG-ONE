"""
NewMenuCallback 单元测试
验证新菜单系统回调的分派逻辑
"""
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
class TestNewMenuCallback:
    @pytest.fixture
    def mock_event(self):
        event = AsyncMock()
        event.chat_id = 123456
        event.answer = AsyncMock()
        event.get_message = AsyncMock()
        event.respond = AsyncMock()
        return event

    async def test_callback_new_menu_handler_main_menu(self, mock_event):
        """测试主菜单回调"""
        from handlers.button.callback.menu_entrypoint import callback_new_menu_handler
        
        with patch('controllers.menu_controller.menu_controller.show_main_menu', new_callable=AsyncMock) as mock_show:
            await callback_new_menu_handler(mock_event, "main_menu", None, None, "new_menu:main_menu")
            mock_show.assert_called_once_with(mock_event)

    async def test_callback_new_menu_handler_forward_hub(self, mock_event):
        """测试转发中心回调"""
        from handlers.button.callback.menu_entrypoint import callback_new_menu_handler
        
        with patch('controllers.menu_controller.menu_controller.show_forward_hub', new_callable=AsyncMock) as mock_show:
            await callback_new_menu_handler(mock_event, "forward_hub", None, None, "new_menu:forward_hub")
            mock_show.assert_called_once_with(mock_event)

    async def test_callback_new_menu_handler_rule_detail(self, mock_event):
        """测试规则详情回调"""
        from handlers.button.callback.menu_entrypoint import callback_new_menu_handler
        
        with patch('controllers.menu_controller.menu_controller.show_rule_detail', new_callable=AsyncMock) as mock_show:
            await callback_new_menu_handler(mock_event, "rule_detail:1", None, None, "new_menu:rule_detail:1")
            mock_show.assert_called_once_with(mock_event, 1)

    async def test_callback_new_menu_handler_history_messages(self, mock_event):
        """测试历史消息菜单回调 (代理到 menu_controller)"""
        from handlers.button.callback.menu_entrypoint import callback_new_menu_handler
        
        with patch('controllers.menu_controller.menu_controller.show_history_messages', new_callable=AsyncMock) as mock_show:
            await callback_new_menu_handler(mock_event, "history_messages", None, None, "new_menu:history_messages")
            mock_show.assert_called_once_with(mock_event)

    async def test_callback_new_menu_handler_duration_picker(self, mock_event):
        """测试时长选择器回调 (曾导致 AttributeError)"""
        from handlers.button.callback.menu_entrypoint import callback_new_menu_handler
        
        with patch('handlers.button.callback.menu_entrypoint.new_menu_system.show_duration_range_picker', new_callable=AsyncMock) as mock_show:
            # menu_entrypoint.py 内部处理 set_duration_start
            await callback_new_menu_handler(mock_event, "set_duration_start", None, None, "new_menu:set_duration_start")
            mock_show.assert_called_once_with(mock_event, "min")

    async def test_callback_new_menu_handler_forward_search(self, mock_event):
        """测试转发搜索回调"""
        from handlers.button.callback.menu_entrypoint import callback_new_menu_handler
        
        with patch('handlers.button.callback.menu_entrypoint.new_menu_system.show_forward_search', new_callable=AsyncMock) as mock_show:
            await callback_new_menu_handler(mock_event, "forward_search", None, None, "new_menu:forward_search")
            mock_show.assert_called_once_with(mock_event)
