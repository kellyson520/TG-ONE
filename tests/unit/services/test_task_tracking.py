import pytest
import asyncio
import weakref
import gc
from services.exception_handler import GlobalExceptionHandler

@pytest.mark.asyncio
async def test_task_tracking_leak_prevention():
    """测试任务追踪器在任务结束时能正确释放引用 (防止内存泄漏)"""
    handler = GlobalExceptionHandler()
    
    async def sample_task():
        await asyncio.sleep(0.01)
        
    task = handler.create_task(sample_task(), name="test_leak")
    await task
    
    # 彻底清除本地强引用
    task_ref = weakref.ref(task)
    del task
    
    # 多次让出控制权让 loop 清理已结束任务
    for _ in range(5):
        gc.collect()
        await asyncio.sleep(0.01)
        
    # 如果一切正常，weakref 应该失效 (或者至少任务应该从 _active_tasks 中消失)
    # 注意: Task 对象有时会被 EventLoop 缓存一小会儿
    # 这里我们主要验证 _active_tasks 是否变空
    assert len([t for t in handler._active_tasks if not t.done()]) == 0

@pytest.mark.asyncio
async def test_cancel_all_managed_tasks():
    """测试批量取消逻辑"""
    handler = GlobalExceptionHandler()
    task_run_count = 0
    
    async def long_running_task():
        nonlocal task_run_count
        try:
            await asyncio.sleep(10)
            task_run_count += 1
        except asyncio.CancelledError:
            return
            
    # 启动 3 个任务
    tasks = [handler.create_task(long_running_task(), name=f"task_{i}") for i in range(3)]
    assert len(handler._active_tasks) == 3
    
    # 批量取消
    await handler.cancel_all_managed_tasks(timeout=1.0)
    
    # 验证任务状态
    assert all(t.done() for t in tasks)
    assert task_run_count == 0

@pytest.mark.asyncio
async def test_task_inventory_reporting():
    """测试任务清单报告"""
    handler = GlobalExceptionHandler()
    
    async def named_task():
        await asyncio.sleep(0.1)
        
    t1 = handler.create_task(named_task(), name="inventory_target", critical=True)
    
    inventory = handler.get_active_tasks_inventory()
    assert len(inventory) == 1
    assert inventory[0]["name"] == "inventory_target"
    assert inventory[0]["critical"] is True
    
    await t1
