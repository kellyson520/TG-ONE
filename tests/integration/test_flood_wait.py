
"""
FloodWait 机制专项测试
测试 Telegram 限流机制的解析、状态记录与冷却逻辑
"""

import pytest
import time
from unittest.mock import AsyncMock, patch
from services.queue_service import (
    forward_messages_queued, 
    _flood_wait_until
)

# 模拟 Telethon 的 FloodWaitError
class MockFloodWaitError(Exception):
    def __init__(self, seconds):
        self.seconds = seconds
        super().__init__(f"A wait of {seconds} seconds is required")

# 模拟只有字符串信息的普通错误
class MockFloodWaitStringException(Exception):
    pass

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.forward_messages = AsyncMock()
    return client

@pytest.fixture(autouse=True)
def cleanup_flood_wait_state():
    """每次测试前清理全局 FloodWait 状态"""
    _flood_wait_until.clear()
    yield
    _flood_wait_until.clear()

@pytest.mark.asyncio
async def test_flood_wait_attribute_parsing(mock_client):
    """测试标准 Telethon 异常属性解析"""
    # 模拟第一次调用抛出 FloodWait (10s)
    mock_client.forward_messages.side_effect = MockFloodWaitError(10)
    
    target_chat_id = 12345
    target_key = str(target_chat_id)
    
    # 预期函数会捕获异常，记录状态，并重新抛出异常
    with pytest.raises(Exception) as exc:
        await forward_messages_queued(
            client=mock_client,
            source_chat_id=111,
            target_chat_id=target_chat_id,
            messages=[1]
        )
    
    # 验证状态是否已更新
    assert target_key in _flood_wait_until
    # 允许一定的执行时间误差，截止时间应在未来 9-11秒 之间 (考虑 jitter)
    remaining = _flood_wait_until[target_key] - time.time()
    assert 8.0 < remaining < 13.0  # 10s * (0.8~1.2) jitter

@pytest.mark.asyncio
async def test_flood_wait_string_parsing(mock_client):
    """测试字符串正则解析 (针对非标准异常)"""
    # 模拟抛出包含秒数的字符串异常
    mock_client.forward_messages.side_effect = MockFloodWaitStringException("FloodWait of 42 seconds required")
    
    target_chat_id = 67890
    target_key = str(target_chat_id)
    
    with pytest.raises(MockFloodWaitStringException):
        await forward_messages_queued(
            client=mock_client,
            source_chat_id=111,
            target_chat_id=target_chat_id,
            messages=[1]
        )
        
    # 验证是否成功解析出 42 秒
    assert target_key in _flood_wait_until
    remaining = _flood_wait_until[target_key] - time.time()
    # 42 * 0.8 = 33.6, 42 * 1.2 = 50.4
    assert 33.0 < remaining < 51.0

@pytest.mark.asyncio
async def test_blocking_behavior(mock_client):
    """测试冷却期内的阻塞行为"""
    target_chat_id = 99999
    target_key = str(target_chat_id)
    
    # 手动设置一个未来的冷却时间 (5秒后)
    future_time = time.time() + 2.0
    _flood_wait_until[target_key] = future_time
    
    mock_client.forward_messages.return_value = "success"
    
    start_time = time.time()
    
    # 执行发送 - 内部应该会 sleep 直到冷却结束
    await forward_messages_queued(
        client=mock_client,
        source_chat_id=111,
        target_chat_id=target_chat_id,
        messages=[1],
        handle_flood_wait_sleep=True
    )
    
    duration = time.time() - start_time
    
    # 验证确实等待了约 2 秒
    assert duration >= 1.9

@pytest.mark.asyncio
async def test_backoff_retry_success(mock_client):
    """测试常规错误的指数退避重试"""
    # 模拟前两次失败，第三次成功
    mock_client.forward_messages.side_effect = [
        Exception("Network error"),
        Exception("Server busy"),
        "success"
    ]
    
    await forward_messages_queued(
        client=mock_client,
        source_chat_id=111,
        target_chat_id=1000,
        messages=[1]
    )
    
    # 验证调用了3次
    assert mock_client.forward_messages.call_count == 3

@pytest.mark.asyncio
async def test_batch_forward_fallback(mock_client):
    """测试批量转发失败后的回退机制"""
    # 启用批量 API
    def mock_getenv(key, default=None):
        if key == "FORWARD_ENABLE_BATCH_API":
            return "true"
        if key == "FORWARD_MAX_BATCH_SIZE":
            return "50"
        return default or "0"

    with patch('os.getenv', side_effect=mock_getenv):
        # 模拟 api_optimizer.forward_messages_batch 失败
        with patch('services.network.telegram_api_optimizer.api_optimizer.forward_messages_batch') as mock_batch:
            mock_batch.side_effect = Exception("Batch failed")
            
            # 单条转发成功
            mock_client.forward_messages.return_value = "success"
            
            await forward_messages_queued(
                client=mock_client,
                source_chat_id=111,
                target_chat_id=2000,
                messages=[1, 2, 3], # 多条消息触发批量
                handle_flood_wait_sleep=False
            )
            
            # 验证批量被调用
            assert mock_batch.called
            # 验证回退到单条调用 (3次)
            assert mock_client.forward_messages.call_count == 3
