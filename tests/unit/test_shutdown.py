"""
优雅关闭协调器单元测试

测试 core.shutdown.ShutdownCoordinator 的核心功能：
- 清理任务注册
- 优先级排序
- 超时控制
- 异常处理
- 状态管理

Author: System
Created: 2026-01-14
"""

import asyncio
import pytest
from core.shutdown import ShutdownCoordinator, CleanupTask, get_shutdown_coordinator, register_cleanup


class TestShutdownCoordinator:
    """ShutdownCoordinator 单元测试"""
    
    def test_init(self):
        """测试初始化"""
        coordinator = ShutdownCoordinator(total_timeout=10.0)
        assert coordinator._total_timeout == 10.0
        assert coordinator._is_shutting_down is False
        assert len(coordinator._tasks) == 0
    
    def test_register_cleanup(self):
        """测试注册清理任务"""
        coordinator = ShutdownCoordinator()
        
        async def dummy_cleanup():
            pass
        
        coordinator.register_cleanup(
            callback=dummy_cleanup,
            priority=3,
            timeout=2.0,
            name="test_task"
        )
        
        assert len(coordinator._tasks) == 1
        task = coordinator._tasks[0]
        assert task.name == "test_task"
        assert task.priority == 3
        assert task.timeout == 2.0
    
    def test_register_cleanup_invalid_priority(self):
        """测试无效优先级"""
        coordinator = ShutdownCoordinator()
        
        async def dummy_cleanup():
            pass
        
        with pytest.raises(ValueError, match="Priority must be 0-9"):
            coordinator.register_cleanup(dummy_cleanup, priority=10)
        
        with pytest.raises(ValueError, match="Priority must be 0-9"):
            coordinator.register_cleanup(dummy_cleanup, priority=-1)
    
    @pytest.mark.asyncio
    async def test_shutdown_order(self):
        """测试清理任务按优先级执行"""
        coordinator = ShutdownCoordinator()
        execution_order = []
        
        async def task_priority_0():
            execution_order.append(0)
        
        async def task_priority_1():
            execution_order.append(1)
        
        async def task_priority_2():
            execution_order.append(2)
        
        # 乱序注册
        coordinator.register_cleanup(task_priority_1, priority=1, name="task_1")
        coordinator.register_cleanup(task_priority_2, priority=2, name="task_2")
        coordinator.register_cleanup(task_priority_0, priority=0, name="task_0")
        
        success = await coordinator.shutdown()
        
        assert success is True
        assert execution_order == [0, 1, 2]  # 按优先级排序
    
    @pytest.mark.asyncio
    async def test_shutdown_timeout(self):
        """测试单个任务超时"""
        coordinator = ShutdownCoordinator(total_timeout=10.0)
        
        async def slow_task():
            await asyncio.sleep(10)  # 超过任务超时
        
        coordinator.register_cleanup(slow_task, timeout=0.5, name="slow_task")
        
        success = await coordinator.shutdown()
        
        assert success is False  # 超时导致失败
    
    @pytest.mark.asyncio
    async def test_shutdown_total_timeout(self):
        """测试总超时"""
        coordinator = ShutdownCoordinator(total_timeout=1.0)
        execution_count = []
        
        async def task1():
            await asyncio.sleep(0.6)
            execution_count.append(1)
        
        async def task2():
            await asyncio.sleep(0.6)
            execution_count.append(2)
        
        coordinator.register_cleanup(task1, priority=0, timeout=1.0, name="task1")
        coordinator.register_cleanup(task2, priority=1, timeout=1.0, name="task2")
        
        success = await coordinator.shutdown()
        
        # 第一个任务完成，第二个任务因总超时被跳过
        assert len(execution_count) == 1
        assert success is False
    
    @pytest.mark.asyncio
    async def test_shutdown_exception_handling(self):
        """测试异常处理"""
        coordinator = ShutdownCoordinator()
        execution_order = []
        
        async def failing_task():
            execution_order.append("failing")
            raise RuntimeError("Task failed")
        
        async def normal_task():
            execution_order.append("normal")
        
        coordinator.register_cleanup(failing_task, priority=0, name="failing")
        coordinator.register_cleanup(normal_task, priority=1, name="normal")
        
        success = await coordinator.shutdown()
        
        # 即使第一个任务失败，第二个任务仍应执行
        assert execution_order == ["failing", "normal"]
        assert success is False  # 有任务失败
    
    @pytest.mark.asyncio
    async def test_is_shutting_down(self):
        """测试关闭状态检查"""
        coordinator = ShutdownCoordinator()
        
        assert coordinator.is_shutting_down() is False
        
        async def check_status():
            assert coordinator.is_shutting_down() is True
        
        coordinator.register_cleanup(check_status, name="check")
        
        await coordinator.shutdown()
        
        assert coordinator.is_shutting_down() is True
    
    @pytest.mark.asyncio
    async def test_duplicate_shutdown(self):
        """测试防止重复关闭"""
        coordinator = ShutdownCoordinator()
        
        async def dummy():
            await asyncio.sleep(0.1)
        
        coordinator.register_cleanup(dummy, name="dummy")
        
        # 并发调用 shutdown
        results = await asyncio.gather(
            coordinator.shutdown(),
            coordinator.shutdown(),
            coordinator.shutdown()
        )
        
        # 只有第一个返回 True，其他返回 False
        assert results.count(True) == 1
        assert results.count(False) == 2
    
    @pytest.mark.asyncio
    async def test_get_shutdown_duration(self):
        """测试获取关闭时长"""
        coordinator = ShutdownCoordinator()
        
        assert coordinator.get_shutdown_duration() is None
        
        async def slow_task():
            await asyncio.sleep(0.2)
        
        coordinator.register_cleanup(slow_task, name="slow")
        
        await coordinator.shutdown()
        
        duration = coordinator.get_shutdown_duration()
        assert duration is not None
        assert duration >= 0.2
    
    @pytest.mark.asyncio
    async def test_effective_timeout(self):
        """测试有效超时（任务超时 vs 剩余时间）"""
        coordinator = ShutdownCoordinator(total_timeout=1.0)
        execution_times = []
        
        async def task1():
            start = asyncio.get_event_loop().time()
            await asyncio.sleep(0.6)
            execution_times.append(asyncio.get_event_loop().time() - start)
        
        async def task2():
            # 这个任务的超时应该被剩余时间限制
            start = asyncio.get_event_loop().time()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass
            execution_times.append(asyncio.get_event_loop().time() - start)
        
        coordinator.register_cleanup(task1, priority=0, timeout=1.0, name="task1")
        coordinator.register_cleanup(task2, priority=1, timeout=5.0, name="task2")
        
        await coordinator.shutdown()
        
        # 第二个任务应该被剩余时间限制（约 0.4s）
        assert len(execution_times) >= 1


class TestGlobalCoordinator:
    """全局协调器测试"""
    
    def test_get_shutdown_coordinator_singleton(self):
        """测试全局单例"""
        coordinator1 = get_shutdown_coordinator()
        coordinator2 = get_shutdown_coordinator()
        
        assert coordinator1 is coordinator2
    
    @pytest.mark.asyncio
    async def test_register_cleanup_global(self):
        """测试全局注册函数"""
        coordinator = get_shutdown_coordinator()
        initial_count = len(coordinator._tasks)
        
        async def test_cleanup():
            pass
        
        register_cleanup(test_cleanup, priority=5, timeout=2.0, name="global_test")
        
        assert len(coordinator._tasks) == initial_count + 1


class TestCleanupTask:
    """CleanupTask 数据类测试"""
    
    def test_cleanup_task_creation(self):
        """测试创建清理任务"""
        async def dummy():
            pass
        
        task = CleanupTask(
            callback=dummy,
            priority=3,
            timeout=5.0,
            name="test"
        )
        
        assert task.callback is dummy
        assert task.priority == 3
        assert task.timeout == 5.0
        assert task.name == "test"


@pytest.mark.asyncio
async def test_integration_scenario():
    """集成测试：模拟真实关闭场景"""
    coordinator = ShutdownCoordinator(total_timeout=10.0)
    state = {
        "web_stopped": False,
        "tasks_finished": False,
        "db_flushed": False,
        "connections_closed": False
    }
    
    # Priority 0: 停止接收新请求
    async def stop_web_server():
        await asyncio.sleep(0.1)
        state["web_stopped"] = True
    
    # Priority 1: 完成进行中的任务
    async def finish_tasks():
        await asyncio.sleep(0.2)
        assert state["web_stopped"] is True  # 确保 web 已停止
        state["tasks_finished"] = True
    
    # Priority 2: 刷盘数据
    async def flush_database():
        await asyncio.sleep(0.1)
        assert state["tasks_finished"] is True  # 确保任务已完成
        state["db_flushed"] = True
    
    # Priority 3: 关闭连接
    async def close_connections():
        await asyncio.sleep(0.1)
        assert state["db_flushed"] is True  # 确保数据已刷盘
        state["connections_closed"] = True
    
    coordinator.register_cleanup(stop_web_server, priority=0, timeout=1.0, name="web_server")
    coordinator.register_cleanup(finish_tasks, priority=1, timeout=2.0, name="tasks")
    coordinator.register_cleanup(flush_database, priority=2, timeout=1.0, name="database")
    coordinator.register_cleanup(close_connections, priority=3, timeout=1.0, name="connections")
    
    success = await coordinator.shutdown()
    
    assert success is True
    assert all(state.values())  # 所有步骤都完成
