"""
User Handler 单元测试 (user_handler.py)
涵盖核心转发逻辑、过滤器链调用及装饰器行为
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Mock modules via a fixture to avoid global pollution
@pytest.fixture(autouse=True, scope="module")
def mock_modules():
    mock_factory_module = MagicMock()
    mock_factory = MagicMock()
    mock_factory_module.get_filter_chain_factory.return_value = mock_factory
    
    mock_unified_cache = MagicMock()
    mock_unified_cache.cached = lambda *a, **k: (lambda f: f)
    
    mock_logger = MagicMock()
    mock_logger_utils = MagicMock()
    mock_logger_utils.get_logger.return_value = mock_logger
    mock_logger_utils.log_performance = lambda *a, **k: (lambda f: f)
    mock_logger_utils.log_user_action = lambda *a, **k: (lambda f: f)
    
    mocks = {
        'mock_factory': mock_factory,
        'mock_logger': mock_logger,
        'filters.factory': mock_factory_module,
        'repositories.db_operations': MagicMock(),
        'core.cache.unified_cache': mock_unified_cache,
        'core.logging': mock_logger_utils,
        'core.helpers.forward_recorder': MagicMock()
    }
    with patch.dict('sys.modules', mocks):
        yield mocks

# Import moved inside tests to ensure mocked context

class TestUserHandler:
    
    @pytest.fixture
    def mock_deps(self):
        """准备通用依赖 Mock"""
        mock_client = AsyncMock()
        mock_event = AsyncMock()
        mock_event.sender.id = 12345
        mock_event.message.text = "Hello"
        mock_rule = MagicMock()
        mock_rule.id = 1
        mock_rule.forward_mode.value = "user"
        mock_rule.user_mode_filters = None
        mock_rule.is_replace = False
        mock_rule.enable_delay = False
        return mock_client, mock_event, mock_rule

    @pytest.mark.asyncio
    async def test_process_forward_rule_basic_flow(self, mock_deps, mock_modules):
        """测试基本的转发规则处理流程 (Happy Path)"""
        mock_client, mock_event, mock_rule = mock_deps
        mock_factory = mock_modules['mock_factory']
        
        with patch('handlers.user_handler.get_filter_chain_factory', return_value=mock_factory):
            from handlers.user_handler import process_forward_rule
            
            # Setup Factory Mock
            mock_chain = AsyncMock()
            mock_chain.process.return_value = {'status': 'processed'}
            mock_factory.create_chain_from_config.return_value = mock_chain
            
            # Call function
            result = await process_forward_rule(mock_client, mock_event, 999, mock_rule)
        
        # Check factory call (Default filters: init, keyword, sender)
        mock_factory.create_chain_from_config.assert_called()
        args = mock_factory.create_chain_from_config.call_args[0]
        filters = args[0]
        assert "keyword" in filters
        assert "sender" in filters
        
        # Check chain execution
        mock_chain.process.assert_called_with(mock_client, mock_event, 999, mock_rule)
        assert result == {'status': 'processed'}
        
    @pytest.mark.asyncio
    async def test_process_forward_rule_custom_config(self, mock_deps, mock_modules):
        """测试自定义过滤器配置"""
        mock_client, mock_event, mock_rule = mock_deps
        mock_rule.user_mode_filters = ["custom_filter"]
        mock_factory = mock_modules['mock_factory']
        
        with patch('handlers.user_handler.get_filter_chain_factory', return_value=mock_factory):
            from handlers.user_handler import process_forward_rule
            mock_chain = AsyncMock()
            mock_factory.create_chain_from_config.return_value = mock_chain
            
            await process_forward_rule(mock_client, mock_event, 999, mock_rule)
        
        mock_factory.create_chain_from_config.assert_called()
        filters = mock_factory.create_chain_from_config.call_args[0][0]
        assert filters == ["custom_filter"]

    @pytest.mark.asyncio
    async def test_process_forward_rule_fallback_flow(self, mock_deps, mock_modules):
        """测试异常导致降级 (Fallback)"""
        mock_client, mock_event, mock_rule = mock_deps
        mock_factory = mock_modules['mock_factory']
        mock_logger = mock_modules['mock_logger']
        
        with patch('handlers.user_handler.get_filter_chain_factory', return_value=mock_factory):
            from handlers.user_handler import process_forward_rule
            
            # Simulate Factory Crash
            mock_factory.create_chain_from_config.side_effect = Exception("Factory Broken")
            
            # Patch local fallback function
            with patch('handlers.user_handler._fallback_process_forward_rule', new_callable=AsyncMock) as mock_fallback:
                mock_fallback.return_value = "fallback_success"
                
                result = await process_forward_rule(mock_client, mock_event, 999, mock_rule)
                
                # Verify Logger
                mock_logger.warning.assert_called()
                assert "崩溃" in mock_logger.warning.call_args[0][0]
                
                # Verify Fallback called
                mock_fallback.assert_called_with(mock_client, mock_event, 999, mock_rule)
                assert result == "fallback_success"
        
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Legacy test harness incompatible with new async decorators. Needs refactor to Integration Test.")
    async def test_fallback_logic_execution(self, mock_deps):
        """测试 _fallback_process_forward_rule 内部执行逻辑"""
