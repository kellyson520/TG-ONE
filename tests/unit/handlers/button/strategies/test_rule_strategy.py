"""
RuleMenuStrategy 单元测试
"""
import pytest
from unittest.mock import AsyncMock, patch
from handlers.button.strategies.rules import RuleMenuStrategy


@pytest.fixture
def rule_strategy():
    return RuleMenuStrategy()


@pytest.fixture
def mock_event():
    event = AsyncMock()
    event.chat_id = 12345
    event.sender_id = 67890
    event.answer = AsyncMock()
    return event


class TestRuleMenuStrategyMatch:
    """测试 RuleMenuStrategy 的 match 方法"""
    
    @pytest.mark.asyncio
    async def test_match_rule_listing(self, rule_strategy):
        """测试规则列表相关action匹配"""
        assert await rule_strategy.match("list_rules") is True
        assert await rule_strategy.match("forward_management") is True
        assert await rule_strategy.match("rule_management") is True
    
    @pytest.mark.asyncio
    async def test_match_rule_detail(self, rule_strategy):
        """测试规则详情相关action匹配"""
        assert await rule_strategy.match("rule_detail") is True
        assert await rule_strategy.match("rule_status") is True
        assert await rule_strategy.match("toggle_rule") is True
    
    @pytest.mark.asyncio
    async def test_match_keyword_actions(self, rule_strategy):
        """测试关键词管理action匹配"""
        assert await rule_strategy.match("keywords") is True
        assert await rule_strategy.match("add_keyword") is True
        assert await rule_strategy.match("clear_keywords_confirm") is True
    
    @pytest.mark.asyncio
    async def test_match_settings_actions(self, rule_strategy):
        """测试规则设置action匹配"""
        assert await rule_strategy.match("rule_basic_settings") is True
        assert await rule_strategy.match("rule_display_settings") is True
        assert await rule_strategy.match("rule_advanced_settings") is True
    
    @pytest.mark.asyncio
    async def test_match_history_actions(self, rule_strategy):
        """测试历史消息相关action匹配"""
        assert await rule_strategy.match("history_messages") is True
        assert await rule_strategy.match("forward_stats_detailed") is True


class TestRuleMenuStrategyHandle:
    """测试 RuleMenuStrategy 的 handle 方法"""
    
    @pytest.mark.asyncio
    async def test_handle_list_rules(self, rule_strategy, mock_event):
        """测试规则列表处理"""
        with patch('handlers.button.strategies.rules.menu_controller') as mock_controller:
            mock_controller.show_rule_list = AsyncMock()
            
            await rule_strategy.handle(mock_event, "list_rules", extra_data=["0"])
            
            mock_controller.show_rule_list.assert_called_once_with(mock_event, page=0)
    
    @pytest.mark.asyncio
    async def test_handle_rule_detail_with_id(self, rule_strategy, mock_event):
        """测试查看规则详情"""
        with patch('handlers.button.strategies.rules.menu_controller') as mock_controller:
            mock_controller.show_rule_detail = AsyncMock()
            
            await rule_strategy.handle(mock_event, "rule_detail", extra_data=["5"])
            
            mock_controller.show_rule_detail.assert_called_once_with(mock_event, 5)
    
    @pytest.mark.asyncio
    async def test_handle_toggle_rule(self, rule_strategy, mock_event):
        """测试切换规则状态"""
        with patch('handlers.button.strategies.rules.menu_controller') as mock_controller:
            mock_controller.toggle_rule_status = AsyncMock()
            
            await rule_strategy.handle(mock_event, "toggle_rule", extra_data=["3"])
            
            mock_controller.toggle_rule_status.assert_called_once_with(mock_event, 3)
    
    @pytest.mark.asyncio
    async def test_handle_keywords(self, rule_strategy, mock_event):
        """测试关键词管理"""
        with patch('handlers.button.strategies.rules.menu_controller') as mock_controller:
            mock_controller.show_manage_keywords = AsyncMock()
            
            await rule_strategy.handle(mock_event, "keywords", extra_data=["7"])
            
            mock_controller.show_manage_keywords.assert_called_once_with(mock_event, 7)
    
    @pytest.mark.asyncio
    async def test_handle_forward_management(self, rule_strategy, mock_event):
        """测试转发管理"""
        with patch('handlers.button.strategies.rules.new_menu_system') as mock_menu:
            mock_menu.show_rule_management = AsyncMock()
            
            await rule_strategy.handle(mock_event, "forward_management")
            
            mock_menu.show_rule_management.assert_called_once_with(mock_event)
    
    @pytest.mark.asyncio
    async def test_handle_history_messages(self, rule_strategy, mock_event):
        """测试历史消息"""
        with patch('handlers.button.strategies.rules.menu_controller') as mock_controller:
            mock_controller.show_history_messages = AsyncMock()
            
            await rule_strategy.handle(mock_event, "history_messages")
            
            mock_controller.show_history_messages.assert_called_once_with(mock_event)
    
    @pytest.mark.asyncio
    async def test_handle_forward_stats_detailed_placeholder(self, rule_strategy, mock_event):
        """测试详细统计占位功能"""
        await rule_strategy.handle(mock_event, "forward_stats_detailed")
        
        mock_event.answer.assert_called_once_with("📊 详细统计功能开发中", alert=True)
