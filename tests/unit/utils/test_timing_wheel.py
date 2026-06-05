import asyncio
import pytest
import time
from services.network.timing_wheel import HashedTimingWheel

@pytest.mark.asyncio
async def test_timing_wheel_execution():
    # 模拟 100ms 一个刻度，共 10 个槽位 (1秒一圈)
    tw = HashedTimingWheel(tick_ms=100, slots=10)
    await tw.start()
    
    results = []
    async def task_cb(val):
        results.append(val)
        
    start_time = time.time()
    # 延迟 300ms
    tw.add_task("t1", 0.3, task_cb, "hello")
    # 延迟 1.2s (跨圈)
    tw.add_task("t2", 1.2, task_cb, "world")
    
    await asyncio.sleep(0.5)
    assert "hello" in results
    assert "world" not in results
    
    await asyncio.sleep(1.0)
    assert "world" in results
    
    await tw.stop()

@pytest.mark.asyncio
async def test_timing_wheel_cancellation():
    tw = HashedTimingWheel(tick_ms=100, slots=10)
    await tw.start()
    
    results = []
    async def task_cb():
        results.append(1)
        
    tw.add_task("cancel_me", 0.5, task_cb)
    tw.cancel_task("cancel_me")
    
    await asyncio.sleep(0.8)
    assert len(results) == 0
    
    await tw.stop()

if __name__ == "__main__":
    asyncio.run(test_timing_wheel_execution())
