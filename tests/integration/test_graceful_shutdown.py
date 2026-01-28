"""
优雅关闭集成测试

测试完整的优雅关闭流程，包括：
- 信号处理
- 多组件协调关闭
- 资源清理验证
- 超时场景

Author: System
Created: 2026-01-14
"""

import asyncio
import pytest
from core.shutdown import ShutdownCoordinator, get_shutdown_coordinator


@pytest.mark.asyncio
async def test_full_shutdown_flow():
    """测试完整的关闭流程"""
    coordinator = ShutdownCoordinator(total_timeout=10.0)
    
    # 模拟各个组件的状态
    state = {
        "web_server_running": True,
        "telegram_connected": True,
        "database_connected": True,
        "tasks_running": 3
    }
    
    # 模拟 Web 服务器关闭
    async def stop_web_server():
        await asyncio.sleep(0.1)
        state["web_server_running"] = False
        assert state["telegram_connected"] is True  # 其他组件还在运行
    
    # 模拟完成运行中的任务
    async def finish_tasks():
        await asyncio.sleep(0.2)
        assert state["web_server_running"] is False  # Web 已停止
        state["tasks_running"] = 0
    
    # 模拟数据库刷盘
    async def flush_database():
        await asyncio.sleep(0.1)
        assert state["tasks_running"] == 0  # 任务已完成
        # 模拟刷盘操作
    
    # 模拟断开 Telegram 连接
    async def disconnect_telegram():
        await asyncio.sleep(0.1)
        state["telegram_connected"] = False
    
    # 模拟关闭数据库连接
    async def close_database():
        await asyncio.sleep(0.1)
        state["database_connected"] = False
    
    # 注册清理回调
    coordinator.register_cleanup(stop_web_server, priority=0, timeout=1.0, name="web_server")
    coordinator.register_cleanup(finish_tasks, priority=1, timeout=2.0, name="tasks")
    coordinator.register_cleanup(flush_database, priority=2, timeout=1.0, name="database_flush")
    coordinator.register_cleanup(disconnect_telegram, priority=3, timeout=1.0, name="telegram")
    coordinator.register_cleanup(close_database, priority=3, timeout=1.0, name="database_close")
    
    # 执行关闭
    success = await coordinator.shutdown()
    
    # 验证
    assert success is True
    assert state["web_server_running"] is False
    assert state["telegram_connected"] is False
    assert state["database_connected"] is False
    assert state["tasks_running"] == 0


@pytest.mark.asyncio
async def test_partial_failure_scenario():
    """测试部分组件失败的场景"""
    coordinator = ShutdownCoordinator(total_timeout=10.0)
    
    cleanup_results = []
    
    async def successful_cleanup():
        cleanup_results.append("success")
    
    async def failing_cleanup():
        cleanup_results.append("attempt_fail")
        raise RuntimeError("Cleanup failed")
    
    async def another_successful_cleanup():
        cleanup_results.append("success_after_fail")
    
    coordinator.register_cleanup(successful_cleanup, priority=0, name="success_1")
    coordinator.register_cleanup(failing_cleanup, priority=1, name="failing")
    coordinator.register_cleanup(another_successful_cleanup, priority=2, name="success_2")
    
    success = await coordinator.shutdown()
    
    # 即使有失败，其他清理仍应执行
    assert success is False  # 整体失败
    assert "success" in cleanup_results
    assert "attempt_fail" in cleanup_results
    assert "success_after_fail" in cleanup_results


@pytest.mark.asyncio
async def test_timeout_scenario():
    """测试超时场景"""
    coordinator = ShutdownCoordinator(total_timeout=2.0)
    
    execution_log = []
    
    async def fast_task():
        execution_log.append("fast_start")
        await asyncio.sleep(0.5)
        execution_log.append("fast_done")
    
    async def slow_task():
        execution_log.append("slow_start")
        await asyncio.sleep(10)  # 超过总超时
        execution_log.append("slow_done")  # 不应执行到这里
    
    async def skipped_task():
        execution_log.append("skipped")  # 不应执行到这里
    
    coordinator.register_cleanup(fast_task, priority=0, timeout=1.0, name="fast")
    coordinator.register_cleanup(slow_task, priority=1, timeout=5.0, name="slow")
    coordinator.register_cleanup(skipped_task, priority=2, timeout=1.0, name="skipped")
    
    success = await coordinator.shutdown()
    
    assert success is False
    assert "fast_start" in execution_log
    assert "fast_done" in execution_log
    assert "slow_start" in execution_log
    assert "slow_done" not in execution_log  # 超时
    assert "skipped" not in execution_log  # 总超时，被跳过


@pytest.mark.asyncio
async def test_concurrent_shutdown_calls():
    """测试并发关闭调用"""
    coordinator = ShutdownCoordinator()
    
    call_count = []
    
    async def cleanup():
        call_count.append(1)
        await asyncio.sleep(0.2)
    
    coordinator.register_cleanup(cleanup, name="cleanup")
    
    # 并发调用
    results = await asyncio.gather(
        coordinator.shutdown(),
        coordinator.shutdown(),
        coordinator.shutdown()
    )
    
    # 只有一个成功
    assert results.count(True) == 1
    assert results.count(False) == 2
    
    # 清理函数只执行一次
    assert len(call_count) == 1


@pytest.mark.asyncio
async def test_shutdown_with_no_tasks():
    """测试没有注册任务的关闭"""
    coordinator = ShutdownCoordinator()
    
    success = await coordinator.shutdown()
    
    assert success is True


@pytest.mark.asyncio
async def test_resource_cleanup_order():
    """测试资源清理顺序的正确性"""
    coordinator = ShutdownCoordinator()
    
    order = []
    
    # 模拟真实场景：必须先停止接收请求，再关闭连接
    async def stop_accepting():
        order.append("stop_accepting")
        await asyncio.sleep(0.05)
    
    async def finish_requests():
        order.append("finish_requests")
        assert "stop_accepting" in order
        await asyncio.sleep(0.05)
    
    async def close_connections():
        order.append("close_connections")
        assert "finish_requests" in order
        await asyncio.sleep(0.05)
    
    # 乱序注册
    coordinator.register_cleanup(close_connections, priority=3, name="close")
    coordinator.register_cleanup(stop_accepting, priority=0, name="stop")
    coordinator.register_cleanup(finish_requests, priority=1, name="finish")
    
    success = await coordinator.shutdown()
    
    assert success is True
    assert order == ["stop_accepting", "finish_requests", "close_connections"]


@pytest.mark.asyncio
async def test_shutdown_duration_tracking():
    """测试关闭时长跟踪"""
    coordinator = ShutdownCoordinator()
    
    async def slow_cleanup():
        await asyncio.sleep(0.3)
    
    coordinator.register_cleanup(slow_cleanup, name="slow")
    
    assert coordinator.get_shutdown_duration() is None
    
    await coordinator.shutdown()
    
    duration = coordinator.get_shutdown_duration()
    assert duration is not None
    assert duration >= 0.3


@pytest.mark.asyncio
async def test_global_coordinator_integration():
    """测试全局协调器集成"""
    from core.shutdown import register_cleanup
    
    coordinator = get_shutdown_coordinator()
    initial_count = len(coordinator._tasks)
    
    async def test_cleanup():
        pass
    
    register_cleanup(test_cleanup, priority=5, timeout=2.0, name="global_test")
    
    assert len(coordinator._tasks) == initial_count + 1


@pytest.mark.asyncio
async def test_exception_in_cleanup_does_not_block():
    """测试清理异常不阻塞其他清理"""
    coordinator = ShutdownCoordinator()
    
    results = []
    
    async def task1():
        results.append(1)
    
    async def failing_task():
        results.append(2)
        raise ValueError("Intentional failure")
    
    async def task3():
        results.append(3)
    
    coordinator.register_cleanup(task1, priority=0, name="task1")
    coordinator.register_cleanup(failing_task, priority=1, name="failing")
    coordinator.register_cleanup(task3, priority=2, name="task3")
    
    success = await coordinator.shutdown()
    
    assert success is False  # 有失败
    assert results == [1, 2, 3]  # 所有任务都执行了


@pytest.mark.asyncio
async def test_effective_timeout_calculation():
    """测试有效超时计算（剩余时间 vs 任务超时）"""
    coordinator = ShutdownCoordinator(total_timeout=1.5)
    
    execution_times = []
    
    async def task1():
        start = asyncio.get_event_loop().time()
        await asyncio.sleep(0.8)
        execution_times.append(asyncio.get_event_loop().time() - start)
    
    async def task2():
        # 这个任务的超时应该被剩余时间限制（约 0.7s）
        start = asyncio.get_event_loop().time()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass
        execution_times.append(asyncio.get_event_loop().time() - start)
    
    coordinator.register_cleanup(task1, priority=0, timeout=1.0, name="task1")
    coordinator.register_cleanup(task2, priority=1, timeout=5.0, name="task2")
    
    await coordinator.shutdown()
    
    # 第一个任务应该完成
    assert len(execution_times) >= 1
    assert execution_times[0] >= 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
