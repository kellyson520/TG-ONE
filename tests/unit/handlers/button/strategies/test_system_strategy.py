"""
SystemMenuStrategy 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from handlers.button.strategies.system import SystemMenuStrategy


@pytest.fixture
def system_strategy():
    """创建 SystemMenuStrategy 实例"""
    return SystemMenuStrategy()


@pytest.fixture
def mock_event():
    """创建模拟的 Telegram 事件"""
    event = AsyncMock()
    event.chat_id = 12345
    event.sender_id = 67890
    event.data = b"new_menu:main_menu"
    event.answer = AsyncMock()
    event.delete = AsyncMock()
    event.edit = AsyncMock()
    return event


class TestSystemMenuStrategyMatch:
    """测试 SystemMenuStrategy 的 match 方法"""
    
    @pytest.mark.asyncio
    async def test_match_main_menu(self, system_strategy):
        """测试主菜单action匹配"""
        assert await system_strategy.match("main_menu") is True
        assert await system_strategy.match("main") is True
        assert await system_strategy.match("main_menu_refresh") is True
    
    @pytest.mark.asyncio
    async def test_match_hub_actions(self, system_strategy):
        """测试中心页面action匹配"""
        assert await system_strategy.match("forward_hub") is True
        assert await system_strategy.match("dedup_hub") is True
        assert await system_strategy.match("analytics_hub") is True
        assert await system_strategy.match("system_hub") is True
    
    @pytest.mark.asyncio
    async def test_match_system_actions(self, system_strategy):
        """测试系统功能action匹配"""
        assert await system_strategy.match("log_viewer") is True
        assert await system_strategy.match("system_status") is True
        assert await system_strategy.match("system_overview") is True
    
    @pytest.mark.asyncio
    async def test_match_backup_actions(self, system_strategy):
        """测试备份相关action匹配"""
        assert await system_strategy.match("db_backup") is True
        assert await system_strategy.match("view_backups") is True
        assert await system_strategy.match("do_backup") is True
    
    @pytest.mark.asyncio
    async def test_no_match_invalid_action(self, system_strategy):
        """测试无效action不匹配"""
        assert await system_strategy.match("invalid_action") is False
        assert await system_strategy.match("random_stuff") is False


class TestSystemMenuStrategyHandle:
    """测试 SystemMenuStrategy 的 handle 方法"""
    
    @pytest.mark.asyncio
    async def test_handle_main_menu(self, system_strategy, mock_event):
        """测试主菜单处理"""
        with patch('controllers.menu_controller.menu_controller') as mock_controller:
            mock_controller.show_main_menu = AsyncMock()
            
            await system_strategy.handle(mock_event, "main_menu")
            
            mock_controller.show_main_menu.assert_called_once_with(mock_event)
    
    @pytest.mark.asyncio
    async def test_handle_main_menu_refresh(self, system_strategy, mock_event):
        """测试主菜单刷新"""
        with patch('controllers.menu_controller.menu_controller') as mock_controller:
            mock_controller.show_main_menu = AsyncMock()
            
            await system_strategy.handle(mock_event, "main_menu_refresh")
            
            mock_controller.show_main_menu.assert_called_once_with(mock_event, force_refresh=True)
            mock_event.answer.assert_called_once_with("✅ 数据看板已刷新")
    
    @pytest.mark.asyncio
    async def test_handle_forward_hub(self, system_strategy, mock_event):
        """测试转发中心"""
        with patch('controllers.menu_controller.menu_controller') as mock_controller:
            mock_controller.show_forward_hub = AsyncMock()
            
            await system_strategy.handle(mock_event, "forward_hub")
            
            mock_controller.show_forward_hub.assert_called_once_with(mock_event)
    
    @pytest.mark.asyncio
    async def test_handle_exit(self, system_strategy, mock_event):
        """测试退出/关闭"""
        await system_strategy.handle(mock_event, "exit")
        mock_event.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_close(self, system_strategy, mock_event):
        """测试关闭"""
        await system_strategy.handle(mock_event, "close")
        mock_event.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_log_viewer(self, system_strategy, mock_event):
        """测试日志查看器"""
        with patch('handlers.button.strategies.system.menu_controller') as mock_controller:
            mock_controller.show_system_logs = AsyncMock()
            
            await system_strategy.handle(mock_event, "log_viewer")
            
            mock_controller.show_system_logs.assert_called_once_with(mock_event)
    
    @pytest.mark.asyncio
    async def test_handle_system_status(self, system_strategy, mock_event):
        """测试系统状态"""
        with patch('handlers.button.strategies.system.new_menu_system') as mock_menu:
            mock_menu.show_system_status = AsyncMock()
            
            await system_strategy.handle(mock_event, "system_status")
            
            mock_menu.show_system_status.assert_called_once_with(mock_event)


class TestSystemMenuStrategyWithExtraData:
    """测试带有额外数据的 handle 处理"""
    
    @pytest.mark.asyncio
    async def test_handle_backup_page_with_page_number(self, system_strategy, mock_event):
        """测试带页码的备份列表"""
        with patch('handlers.button.strategies.system.new_menu_system') as mock_menu:
            mock_menu.show_backup_history = AsyncMock()
            
            await system_strategy.handle(
                mock_event, 
                "backup_page",
                extra_data=["2"]
            )
            
            mock_menu.show_backup_history.assert_called_once_with(mock_event, 2)
    
    @pytest.mark.asyncio
    async def test_handle_restore_backup_with_id(self, system_strategy, mock_event):
        """测试恢复特定备份"""
        with patch('handlers.button.strategies.system.new_menu_system') as mock_menu:
            mock_menu.confirm_restore_backup = AsyncMock()
            
            await system_strategy.handle(
                mock_event,
                "restore_backup",
                extra_data=["5"]
            )
            
            mock_menu.confirm_restore_backup.assert_called_once_with(mock_event, 5)
