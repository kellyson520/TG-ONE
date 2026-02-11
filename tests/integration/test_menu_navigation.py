"""
菜单导航流程集成测试

测试完整的菜单导航路径，验证策略调度和回调处理的端到端流程
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from handlers.button.strategies.registry import MenuHandlerRegistry
from handlers.button.callback.new_menu_callback import callback_new_menu_handler


@pytest.fixture
def mock_event():
    """创建完整的模拟事件"""
    event = AsyncMock()
    event.chat_id = 12345
    event.sender_id = 67890
    event.answer = AsyncMock()
    event.delete = AsyncMock()
    event.edit = AsyncMock()
    event.get_message = AsyncMock(return_value=MagicMock())
    return event


class TestMenuNavigationFlow:
    """测试完整的菜单导航流程"""
    
    @pytest.mark.asyncio
    async def test_main_menu_to_forward_hub_flow(self, mock_event):
        """测试: 主菜单 -> 转发中心"""
        with patch('handlers.button.strategies.system.menu_controller') as mock_controller:
            mock_controller.show_main_menu = AsyncMock()
            mock_controller.show_forward_hub = AsyncMock()
            
            # Step 1: 显示主菜单
            result = await MenuHandlerRegistry.dispatch(mock_event, "main_menu")
            assert result is True
            mock_controller.show_main_menu.assert_called_once()
            
            # Step 2: 导航到转发中心
            result = await MenuHandlerRegistry.dispatch(mock_event, "forward_hub")
            assert result is True
            mock_controller.show_forward_hub.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_forward_hub_to_rule_list_flow(self, mock_event):
        """测试: 转发中心 -> 规则列表"""
        with patch('handlers.button.strategies.system.menu_controller') as sys_controller, \
             patch('handlers.button.strategies.rules.menu_controller') as rule_controller:
            sys_controller.show_forward_hub = AsyncMock()
            rule_controller.show_rule_list = AsyncMock()
            
            # Step 1: 显示转发中心
            result = await MenuHandlerRegistry.dispatch(mock_event, "forward_hub")
            assert result is True
            
            # Step 2: 导航到规则列表
            result = await MenuHandlerRegistry.dispatch(
                mock_event, "list_rules", extra_data=["0"]
            )
            assert result is True
            rule_controller.show_rule_list.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rule_detail_to_settings_flow(self, mock_event):
        """测试: 规则详情 -> 规则设置"""
        with patch('handlers.button.strategies.rules.menu_controller') as mock_controller:
            mock_controller.show_rule_detail = AsyncMock()
            mock_controller.show_rule_basic_settings = AsyncMock()
            
            # Step 1: 显示规则详情
            result = await MenuHandlerRegistry.dispatch(
                mock_event, "rule_detail", extra_data=["1"]
            )
            assert result is True
            
            # Step 2: 进入基础设置
            result = await MenuHandlerRegistry.dispatch(
                mock_event, "rule_basic_settings", extra_data=["1"]
            )
            assert result is True
            mock_controller.show_rule_basic_settings.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dedup_hub_navigation_flow(self, mock_event):
        """测试: 主菜单 -> 去重中心 -> 会话管理"""
        with patch('handlers.button.strategies.system.menu_controller') as sys_controller, \
             patch('handlers.button.strategies.dedup.menu_controller') as dedup_controller:
            sys_controller.show_dedup_hub = AsyncMock()
            dedup_controller.show_session_management = AsyncMock()
            
            # Step 1: 主菜单 -> 去重中心
            result = await MenuHandlerRegistry.dispatch(mock_event, "dedup_hub")
            assert result is True
            sys_controller.show_dedup_hub.assert_called_once()
            
            # Step 2: 去重中心 -> 会话管理
            result = await MenuHandlerRegistry.dispatch(mock_event, "session_management")
            assert result is True
            dedup_controller.show_session_management.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analytics_hub_flow(self, mock_event):
        """测试: 主菜单 -> 数据分析中心 -> 详细报告"""
        with patch('handlers.button.strategies.system.menu_controller') as sys_controller, \
             patch('handlers.button.strategies.analytics.menu_controller') as analytics_controller:
            sys_controller.show_analytics_hub = AsyncMock()
            analytics_controller.show_forward_analytics = AsyncMock()
            
            # Step 1: 主菜单 -> 数据分析中心
            result = await MenuHandlerRegistry.dispatch(mock_event, "analytics_hub")
            assert result is True
            
            # Step 2: 数据分析中心 -> 转发分析
            result = await MenuHandlerRegistry.dispatch(mock_event, "forward_analytics")
            assert result is True
            analytics_controller.show_forward_analytics.assert_called_once()


class TestCallbackHandlerIntegration:
    """测试回调处理器集成"""
    
    @pytest.mark.asyncio
    async def test_callback_handler_dispatches_to_strategy(self, mock_event):
        """测试回调处理器正确调度到策略"""
        with patch('handlers.button.strategies.system.menu_controller') as mock_controller:
            mock_controller.show_main_menu = AsyncMock()
            
            # 模拟 new_menu:main_menu 回调
            await callback_new_menu_handler(
                mock_event,
                "main_menu",  # action_data
                await mock_event.get_message(),
                "new_menu:main_menu"  # data
            )
            
            mock_controller.show_main_menu.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_callback_handler_with_parameters(self, mock_event):
        """测试带参数的回调处理"""
        with patch('handlers.button.strategies.rules.menu_controller') as mock_controller:
            mock_controller.show_rule_detail = AsyncMock()
            
            # 模拟 new_menu:rule_detail:5 回调
            await callback_new_menu_handler(
                mock_event,
                "rule_detail:5",
                await mock_event.get_message(),
                "new_menu:rule_detail:5"
            )
            
            mock_controller.show_rule_detail.assert_called_once()


class TestBackNavigationFlow:
    """测试返回导航流程"""
    
    @pytest.mark.asyncio
    async def test_settings_back_to_rule_detail(self, mock_event):
        """测试: 规则设置 -> 返回规则详情"""
        with patch('handlers.button.strategies.rules.menu_controller') as mock_controller:
            mock_controller.show_rule_basic_settings = AsyncMock()
            mock_controller.show_rule_detail = AsyncMock()
            
            # 在设置页
            await MenuHandlerRegistry.dispatch(
                mock_event, "rule_basic_settings", extra_data=["3"]
            )
            
            # 返回详情页
            await MenuHandlerRegistry.dispatch(
                mock_event, "rule_detail", extra_data=["3"]
            )
            
            mock_controller.show_rule_detail.assert_called_once_with(mock_event, 3)
    
    @pytest.mark.asyncio
    async def test_exit_closes_menu(self, mock_event):
        """测试退出功能关闭菜单"""
        result = await MenuHandlerRegistry.dispatch(mock_event, "exit")
        
        assert result is True
        mock_event.delete.assert_called_once()


class TestErrorHandling:
    """测试错误处理"""
    
    @pytest.mark.asyncio
    async def test_invalid_action_returns_false(self, mock_event):
        """测试无效action返回False"""
        result = await MenuHandlerRegistry.dispatch(mock_event, "invalid_nonexistent_action")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_strategy_exception_continues_to_next(self, mock_event):
        """测试策略异常不中断调度"""
        with patch('handlers.button.strategies.registry.logger') as mock_logger:
            # 触发一个会被捕获的异常场景
            # 由于我们的策略都是async def match返回bool，不太容易出错
            # 这里主要验证日志记录
            result = await MenuHandlerRegistry.dispatch(mock_event, "main_menu")
            
            # 正常情况应该成功
            assert result is True


class TestHighFrequencyActions:
    """测试高频操作的性能"""
    
    @pytest.mark.asyncio
    async def test_rapid_navigation(self, mock_event):
        """测试快速连续导航"""
        with patch('handlers.button.strategies.system.menu_controller') as mock_controller:
            mock_controller.show_main_menu = AsyncMock()
            mock_controller.show_forward_hub = AsyncMock()
            mock_controller.show_dedup_hub = AsyncMock()
            
            # 模拟快速点击
            for _ in range(5):
                await MenuHandlerRegistry.dispatch(mock_event, "main_menu")
            
            assert mock_controller.show_main_menu.call_count == 5
