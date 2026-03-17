import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from core.helpers.batch_sink import TaskStatusSink

@pytest.fixture
def mock_db_manager():
    with patch("core.db_factory.AsyncSessionManager") as mock_manager:
        yield mock_manager

@pytest.fixture
async def sink_instance():
    # 因为是单例模式，清空一下之前可能残留的状态
    sink = TaskStatusSink()
    # 强制清理队列并停止运行态
    while not sink._queue.empty():
        sink._queue.get_nowait()
    sink._running = False
    if sink._daemon_task and not sink._daemon_task.done():
        sink._daemon_task.cancel()
        
    yield sink
    
    # 清理收尾，防止守护协程阻碍事件循环退出
    await sink.stop()

@pytest.mark.asyncio
async def test_singleton():
    sink1 = TaskStatusSink()
    sink2 = TaskStatusSink()
    assert sink1 is sink2, "TaskStatusSink 必须是单例模式"

@pytest.mark.asyncio
async def test_put_item(sink_instance):
    assert sink_instance._queue.empty()
    await sink_instance.put(task_id=1, action='complete')
    await sink_instance.put(task_id=2, action='fail', error_message='TIMEOUT')
    
    assert sink_instance._queue.qsize() == 2
    item1 = sink_instance._queue.get_nowait()
    item2 = sink_instance._queue.get_nowait()
    
    assert item1 == {'id': 1, 'action': 'complete', 'error_message': None}
    assert item2 == {'id': 2, 'action': 'fail', 'error_message': 'TIMEOUT'}

@pytest.mark.asyncio
async def test_flush_process_batch_segregation(sink_instance, mock_db_manager):
    # 构建 Mock 的 AsyncSessionManager
    mock_session = AsyncMock()
    mock_session.execute.return_value.rowcount = 1
    
    # 巧妙构造 AsyncContextManager
    mock_db_manager.return_value.__aenter__.return_value = mock_session
    mock_db_manager.return_value.__aexit__.return_value = None
    
    # 塞入混合的事件
    await sink_instance.put(101, 'complete')
    await sink_instance.put(102, 'fail', 'err')
    await sink_instance.put(103, 'complete')
    
    assert sink_instance._queue.qsize() == 3
    
    # 手动触发 flush 清空池子
    await sink_instance.flush()
    # 等待后台的 process_batch 协程执行完
    await asyncio.sleep(0.1) 
    
    assert sink_instance._queue.empty()
    assert mock_session.commit.called, "必须触发 session.commit()"
    assert mock_session.execute.call_count == 2, "应该触发2次执行，一次处理 complete 批次，一次处理失败"

@pytest.mark.asyncio
async def test_start_stop_lifecycle(sink_instance):
    # 降低心跳间隔加速测试
    sink_instance._flush_interval = 0.05
    
    assert not sink_instance._running
    sink_instance.start()
    assert sink_instance._running
    assert sink_instance._daemon_task is not None
    assert not sink_instance._daemon_task.done()
    
    # 发送几条消息
    await sink_instance.put(201, 'complete')
    await sink_instance.put(202, 'complete')
    
    # 等待 daemon_loop 自动执行一次心跳
    await asyncio.sleep(0.15)
    
    # 断言消息已被自动消费
    assert sink_instance._queue.empty()
    
    # 停止它
    await sink_instance.stop()
    assert not sink_instance._running
    assert sink_instance._daemon_task.done() or sink_instance._daemon_task.cancelled()
