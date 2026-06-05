"""
MenuHandlerRegistry 性能监控单元测试
"""
import pytest
from unittest.mock import AsyncMock
from handlers.button.strategies.registry import MenuHandlerRegistry


@pytest.fixture(autouse=True)
def reset_registry_stats():
    """每个测试前重置统计"""
    MenuHandlerRegistry.reset_stats()
    yield
    MenuHandlerRegistry.reset_stats()


@pytest.fixture
def mock_event():
    event = AsyncMock()
    event.sender_id = 12345
    event.chat_id = 67890
    return event


class TestPerformanceMonitoring:
    """测试性能监控功能"""
    
    @pytest.mark.asyncio
    async def test_records_action_statistics(self, mock_event):
        """测试记录action统计"""
        # 执行几次action
        for _ in range(3):
            await MenuHandlerRegistry.dispatch(mock_event, "main_menu")
        
        # 获取统计
        stats = MenuHandlerRegistry.get_performance_stats()
        
        assert "main_menu" in stats
        assert stats["main_menu"]["count"] == 3
        assert stats["main_menu"]["avg_time"] > 0
        assert stats["main_menu"]["max_time"] > 0
   
    @pytest.mark.asyncio
    async def test_tracks_unmatched_actions(self, mock_event):
        """测试追踪未匹配的actions"""
        # 执行不存在的action
        for _ in range(5):
            await MenuHandlerRegistry.dispatch(mock_event, "nonexistent_action")
        
        # 获取未匹配统计
        unmatched = MenuHandlerRegistry.get_unmatched_actions()
        
        assert "nonexistent_action" in unmatched
        assert unmatched["nonexistent_action"] == 5
    
    @pytest.mark.asyncio
    async def test_calculates_average_time(self, mock_event):
        """测试计算平均执行时间"""
        # 执行多次
        iterations = 10
        for _ in range(iterations):
            await MenuHandlerRegistry.dispatch(mock_event, "main_menu")
        
        stats = MenuHandlerRegistry.get_performance_stats()
        main_menu_stats = stats.get("main_menu")
        
        assert main_menu_stats is not None
        assert main_menu_stats["count"] == iterations
        # 平均时间应该是总时间除以次数
        expected_avg = main_menu_stats["total_time"] / iterations
        assert abs(main_menu_stats["avg_time"] - expected_avg) < 0.0001
    
    @pytest.mark.asyncio
    async def test_tracks_max_execution_time(self, mock_event):
        """测试追踪最大执行时间"""
        await MenuHandlerRegistry.dispatch(mock_event, "forward_hub")
        
        stats = MenuHandlerRegistry.get_performance_stats()
        forward_stats = stats.get("forward_hub")
        
        assert forward_stats is not None
        assert forward_stats["max_time"] > 0
        assert forward_stats["max_time"] >= forward_stats["avg_time"]
    
    @pytest.mark.asyncio
    async def test_high_frequency_actions_identified(self, mock_event):
        """测试高频actions被正确识别"""
        high_freq_actions = MenuHandlerRegistry.HIGH_FREQUENCY_ACTIONS
        
        assert "main_menu" in high_freq_actions
        assert "forward_hub" in high_freq_actions
        assert "list_rules" in high_freq_actions
    
    def test_reset_stats_clears_data(self):
        """测试重置统计清除数据"""
        # stats已经在 autouse fixture中被重置
        assert len(MenuHandlerRegistry.get_performance_stats()) == 0
        assert len(MenuHandlerRegistry.get_unmatched_actions()) == 0
    
    @pytest.mark.asyncio
    async def test_get_top_n_stats(self, mock_event):
        """测试获取Top N统计"""
        # 执行多个不同的actions
        actions = ["main_menu", "forward_hub", "dedup_hub", "analytics_hub"]
        for i, action in enumerate(actions):
            for _ in range(i + 1):  # 不同的执行次数
                await MenuHandlerRegistry.dispatch(mock_event, action)
        
        # 获取Top 2
        top_2 = MenuHandlerRegistry.get_performance_stats(top_n=2)
        
        assert len(top_2) == 2
        # 应该按count排序，analytics_hub最多(4次)
        assert "analytics_hub" in top_2
        assert "dedup_hub" in top_2


class TestErrorTracking:
    """测试错误追踪功能"""
    
    @pytest.mark.asyncio
    async def test_unmatched_action_logged_at_thresholds(self, mock_event, caplog):
        """测试未匹配action在阈值时记录日志"""
        import logging
        caplog.set_level(logging.ERROR)
        
        # 执行1次 (阈值)
        await MenuHandlerRegistry.dispatch(mock_event, "test_unmatched")
        assert any("[UNMATCHED]" in record.message for record in caplog.records)
        
        caplog.clear()
        
        # 再执行4次，到达5次阈值
        for _ in range(4):
            await MenuHandlerRegistry.dispatch(mock_event, "test_unmatched")
        
        assert any("5 times" in record.message for record in caplog.records)


class TestRegistryBasics:
    """测试基本的注册表功能"""
    
    def test_get_registered_handlers(self):
        """测试获取已注册的处理器"""
        handlers = MenuHandlerRegistry.get_registered_handlers()
        
        assert isinstance(handlers, list)
        assert len(handlers) > 0
        # 应该包含我们已知的策略
        assert "SystemMenuStrategy" in handlers
        assert "RuleMenuStrategy" in handlers
    
    @pytest.mark.asyncio
    async def test_dispatch_returns_true_for_valid_action(self, mock_event):
        """测试有效action返回True"""
        result = await MenuHandlerRegistry.dispatch(mock_event, "main_menu")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_dispatch_returns_false_for_invalid_action(self, mock_event):
        """测试无效action返回False"""
        result = await MenuHandlerRegistry.dispatch(mock_event, "totally_invalid")
        assert result is False
