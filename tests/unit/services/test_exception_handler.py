"""
GlobalExceptionHandler 单元测试

测试:
- 异常聚合
- 异常捕捉任务包装器
- 回调钩子
- 统计信息

创建于: 2026-01-11
Phase G.2 测试
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch


class TestGlobalExceptionHandler:
    """GlobalExceptionHandler 单元测试"""
    
    @pytest.fixture
    def handler(self):
        """创建新的异常处理器实例"""
        from services.exception_handler import GlobalExceptionHandler
        return GlobalExceptionHandler()
    
    def test_init(self, handler):
        """测试初始化"""
        assert handler._running is False
        assert len(handler._aggregates) == 0
        assert len(handler._callbacks) == 0
    
    def test_compute_exception_hash(self, handler):
        """测试异常哈希计算"""
        exc1 = ValueError("test error")
        exc2 = ValueError("test error")
        exc3 = ValueError("different error")
        exc4 = TypeError("test error")
        
        hash1 = handler._compute_exception_hash(exc1)
        hash2 = handler._compute_exception_hash(exc2)
        hash3 = handler._compute_exception_hash(exc3)
        hash4 = handler._compute_exception_hash(exc4)
        
        # 相同类型和消息应该生成相同的哈希
        assert hash1 == hash2
        # 不同消息应该生成不同的哈希
        assert hash1 != hash3
        # 不同类型应该生成不同的哈希
        assert hash1 != hash4
    
    @pytest.mark.asyncio
    async def test_handle_exception_first_time(self, handler):
        """测试首次处理异常"""
        exc = ValueError("test error")
        
        with patch.object(handler, '_log_exception', new_callable=AsyncMock) as mock_log:
            with patch.object(handler, '_invoke_callbacks', new_callable=AsyncMock):
                result = await handler.handle_exception(exc, task_name="test_task")
        
        # 首次异常应该被记录
        assert result is True
        mock_log.assert_called_once()
        
        # 应该有一个聚合记录
        assert len(handler._aggregates) == 1
    
    @pytest.mark.asyncio
    async def test_handle_exception_aggregation(self, handler):
        """测试异常聚合"""
        exc = ValueError("test error")
        
        with patch.object(handler, '_log_exception', new_callable=AsyncMock):
            with patch.object(handler, '_invoke_callbacks', new_callable=AsyncMock):
                # 首次
                result1 = await handler.handle_exception(exc)
                # 第二次 (应该被聚合)
                result2 = await handler.handle_exception(exc)
                result3 = await handler.handle_exception(exc)
        
        assert result1 is True  # 首次记录
        assert result2 is False  # 被聚合
        assert result3 is False  # 被聚合
        
        # 聚合计数应该增加
        exc_hash = handler._compute_exception_hash(exc)
        assert handler._aggregates[exc_hash].count == 3
    
    @pytest.mark.asyncio
    async def test_create_task_success(self, handler):
        """测试创建任务 - 成功情况"""
        async def successful_task():
            return "success"
        
        task = handler.create_task(successful_task(), name="test_task")
        result = await task
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_create_task_with_exception(self, handler):
        """测试创建任务 - 异常情况"""
        async def failing_task():
            raise ValueError("task failed")
        
        with patch.object(handler, 'handle_exception', new_callable=AsyncMock) as mock_handle:
            task = handler.create_task(failing_task(), name="failing_task")
            
            with pytest.raises(ValueError):
                await task
            
            # 异常应该被处理
            mock_handle.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_task_cancellation(self, handler):
        """测试任务取消"""
        async def long_task():
            await asyncio.sleep(10)
        
        task = handler.create_task(long_task(), name="long_task")
        await asyncio.sleep(0.01)
        task.cancel()
        
        with pytest.raises(asyncio.CancelledError):
            await task
    
    def test_add_callback(self, handler):
        """测试添加回调"""
        def my_callback(exc, context, task_name):
            pass
        
        handler.add_callback(my_callback)
        assert len(handler._callbacks) == 1
        assert my_callback in handler._callbacks
    
    def test_remove_callback(self, handler):
        """测试移除回调"""
        def my_callback(exc, context, task_name):
            pass
        
        handler.add_callback(my_callback)
        handler.remove_callback(my_callback)
        assert len(handler._callbacks) == 0
    
    @pytest.mark.asyncio
    async def test_invoke_callbacks(self, handler):
        """测试回调调用"""
        callback_called = []
        
        async def async_callback(exc, context, task_name):
            callback_called.append(("async", exc, task_name))
        
        def sync_callback(exc, context, task_name):
            callback_called.append(("sync", exc, task_name))
        
        handler.add_callback(async_callback)
        handler.add_callback(sync_callback)
        
        exc = ValueError("test")
        await handler._invoke_callbacks(exc, None, "test_task")
        
        assert len(callback_called) == 2
    
    def test_get_stats(self, handler):
        """测试获取统计"""
        stats = handler.get_stats()
        
        assert "total_aggregates" in stats
        assert "active_aggregates" in stats
        assert "callbacks_count" in stats
        assert "aggregation_window_minutes" in stats
        assert "recent_exceptions" in stats
    
    def test_task_wrapper_decorator(self, handler):
        """测试任务包装器装饰器"""
        @handler.task_wrapper("decorated_task")
        async def my_task():
            return "decorated"
        
        assert asyncio.iscoroutinefunction(my_task)


class TestExceptionAggregate:
    """ExceptionAggregate 单元测试"""
    
    def test_init(self):
        """测试初始化"""
        from services.exception_handler import ExceptionAggregate
        
        agg = ExceptionAggregate("test_hash", "test traceback")
        
        assert agg.exception_hash == "test_hash"
        assert agg.count == 1
        assert agg.sample_traceback == "test traceback"
        assert agg.first_occurrence is not None
        assert agg.last_occurrence is not None
    
    def test_increment(self):
        """测试计数增加"""
        from services.exception_handler import ExceptionAggregate
        
        agg = ExceptionAggregate("test_hash", "test traceback")
        old_last = agg.last_occurrence
        
        agg.increment()
        
        assert agg.count == 2
        assert agg.last_occurrence >= old_last
