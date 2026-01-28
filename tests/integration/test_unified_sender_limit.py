
"""
UnifiedSender 限流保护集成测试
验证 Copy Mode (UnifiedSender) 是否正确接入了限流与 FloodWait 保护机制
"""

import pytest
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock
from core.helpers.unified_sender import UnifiedSender
from services.queue_service import _flood_wait_until

class MockFloodWaitError(Exception):
    def __init__(self, seconds):
        self.seconds = seconds
        super().__init__(f"FloodWait for {seconds} seconds")

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.send_message = AsyncMock()
    client.send_file = AsyncMock()
    return client

@pytest.fixture(autouse=True)
def cleanup_flood_wait():
    _flood_wait_until.clear()
    yield
    _flood_wait_until.clear()

@pytest.mark.asyncio
async def test_unified_sender_text_flood_wait(mock_client):
    """测试发送文本时的 FloodWait 保护 (预期抛出异常并设置冷却)"""
    sender = UnifiedSender(mock_client)
    
    # 模拟第一次失败 (FloodWait 2s)
    mock_client.send_message.side_effect = MockFloodWaitError(2)
    
    target_id = 991
    start_time = time.time()
    
    # 第一次调用应抛出异常
    with pytest.raises(MockFloodWaitError):
        await sender.send(target_id, text="Hello Limit")
    
    # 验证状态已记录
    assert str(target_id) in _flood_wait_until
    
    # 验证冷却时间 (2s * 0.8 jitter ~ 1.6s)
    wait_until = _flood_wait_until[str(target_id)]
    assert wait_until > start_time + 1.5
    
    # 测试第二次调用被阻塞
    # 恢复正常
    mock_client.send_message.side_effect = None
    mock_client.send_message.return_value = "ok"
    
    start_time_2 = time.time()
    await sender.send(target_id, text="Hello again")
    duration = time.time() - start_time_2
    
    # 此时应该还在冷却中，所以会 wait
    # 实际 wait 时间 = wait_until - now
    # 至少应该稍微等待一下
    assert duration > 0.05
    
@pytest.mark.asyncio
async def test_unified_sender_media_flood_wait(mock_client):
    """测试发送媒体时的 FloodWait 保护"""
    sender = UnifiedSender(mock_client)
    mock_media = MagicMock()
    
    mock_client.send_file.side_effect = MockFloodWaitError(1)
    
    target_id = 992
    
    with pytest.raises(MockFloodWaitError):
        await sender.send(target_id, media=mock_media, text="Caption")
        
    assert str(target_id) in _flood_wait_until

@pytest.mark.asyncio
async def test_unified_sender_album_concurrency(mock_client):
    """测试多个并发发送请求是否被串行化 (针对同一目标)"""
    sender = UnifiedSender(mock_client)
    
    # 模拟每次发送耗时 0.2s
    async def slow_send(*args, **kwargs):
        await asyncio.sleep(0.2)
        return "ok"
    
    mock_client.send_message.side_effect = slow_send
    
    target_id = 993
    tasks = []
    
    start_time = time.time()
    
    # 发起3个并发请求
    for i in range(3):
        tasks.append(sender.send(target_id, text=f"Msg {i}"))
        
    await asyncio.gather(*tasks)
    
    duration = time.time() - start_time
    
    # 如果是串行，总耗时应 >= 0.6s
    # 如果是并行，总耗时 ~0.2s
    # Per-target default limit is 2 (from forward_queue.py defaults or env)
    # _TARGET_LIMIT defaults to 2.
    # So 2 run in parallel (0.2s), then 1 runs (0.2s). Total ~0.4s.
    
    # wait, checks forward_queue.py default:
    # _TARGET_LIMIT = _int_env("FORWARD_MAX_CONCURRENCY_PER_TARGET", 2)
    
    # To verify locking works, we expect stricter behavior if limit is 1.
    # But even with 2, duration should be roughly 0.4s, definitely > 0.2s
    assert duration >= 0.35 

@pytest.mark.asyncio
async def test_unified_sender_detached_buttons(mock_client):
    """测试 Album 分离按钮的发送逻辑"""
    sender = UnifiedSender(mock_client)
    mock_client.send_file.return_value = "media_ok"
    mock_client.send_message.return_value = "btn_ok"
    
    mock_album = [MagicMock(), MagicMock()]
    buttons = [[MagicMock()]]
    
    await sender.send(123, media=mock_album, buttons=buttons)
    
    # send_file (album) called
    assert mock_client.send_file.called
    # send_message (buttons) called
    assert mock_client.send_message.called
    
    # 验证按钮消息包含正确文本
    args = mock_client.send_message.call_args
    assert "互动按钮" in args[0][1]
