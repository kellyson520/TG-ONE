"""
Core Container 测试
测试依赖注入容器的基本功能
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestContainer:
    """测试 Container 核心功能"""
    
    def test_container_initialization(self):
        """测试容器初始化"""
        # 由于 Container 在导入时会实例化，我们测试它的存在性
        from core.container import container
        
        assert container is not None
        assert hasattr(container, 'db')
        assert hasattr(container, 'bus')
    
    def test_container_has_repositories(self):
        """测试容器包含所有仓库"""
        from core.container import container
        
        assert hasattr(container, 'task_repo')
        assert hasattr(container, 'rule_repo')
        assert hasattr(container, 'stats_repo')
        assert hasattr(container, 'user_repo')
    
    @pytest.mark.asyncio
    async def test_container_lifecycle(self):
        """测试容器生命周期管理"""
        from core.container import Container
        
        # 创建一个新的容器实例用于测试
        test_container = Container()
        
        # 验证基础组件已初始化
        assert test_container.db is not None
        assert test_container.bus is not None
        
        # 注意: 不测试 init_with_client 因为它需要真实的 Telegram client


class TestEventBus:
    """测试事件总线"""
    
    @pytest.mark.asyncio
    async def test_event_bus_subscribe_and_publish(self):
        """测试事件订阅和发布"""
        from core.event_bus import EventBus
        
        bus = EventBus()
        callback_called = False
        received_data = None
        
        async def test_callback(data):
            nonlocal callback_called, received_data
            callback_called = True
            received_data = data
        
        # 订阅事件
        bus.subscribe("TEST_EVENT", test_callback)
        
        # 发布事件 (wait=True 确保同步执行)
        test_data = {"message": "test"}
        await bus.publish("TEST_EVENT", test_data, wait=True)
        
        # 验证回调被调用
        assert callback_called
        assert received_data == test_data


class TestPipeline:
    """测试消息处理管道"""
    
    @pytest.mark.asyncio
    async def test_pipeline_add_middleware(self):
        """测试添加中间件到管道"""
        from core.pipeline import Pipeline
        from unittest.mock import MagicMock
        
        pipeline = Pipeline()
        mock_middleware = MagicMock()
        
        pipeline.add(mock_middleware)
        
        # 验证中间件被添加
        assert len(pipeline.middlewares) == 1
        assert pipeline.middlewares[0] == mock_middleware
    
    @pytest.mark.asyncio
    async def test_pipeline_execute(self):
        """测试管道执行"""
        from core.pipeline import Pipeline, MessageContext
        
        pipeline = Pipeline()
        
        # 创建一个简单的中间件
        class TestMiddleware:
            async def process(self, ctx, next_middleware):
                ctx.metadata['processed'] = True
                if next_middleware:
                    await next_middleware()
        
        pipeline.add(TestMiddleware())
        
        # 执行管道 - 使用正确的参数
        ctx = MessageContext(
            client=MagicMock(),
            task_id=1,
            chat_id=123,
            message_id=456,
            message_obj=MagicMock()
        )
        await pipeline.execute(ctx)
        
        # 验证上下文被处理
        assert ctx.metadata.get('processed') is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
