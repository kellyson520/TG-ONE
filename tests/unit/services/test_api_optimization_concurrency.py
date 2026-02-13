
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from services.network.api_optimization import TelegramAPIOptimizer
from telethon.tl.types import Channel
import time

@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client

@pytest.fixture
def optimizer(mock_client):
    return TelegramAPIOptimizer(mock_client)

@pytest.mark.asyncio
async def test_request_coalescing(optimizer, mock_client):
    """验证请求合并 (Singleflight): 多个并发请求同一 ID，实际只调用一次 API"""
    
    # 设置 Mock 返回
    mock_entity = MagicMock(spec=Channel)
    mock_entity.id = 999
    mock_client.get_entity.return_value = mock_entity
    
    mock_full_chat = MagicMock()
    mock_full_chat.full_chat = MagicMock()
    mock_full_chat.full_chat.read_inbox_max_id = 50
    # 模拟 API 耗时
    async def slow_api_call(*args, **kwargs):
        await asyncio.sleep(0.5)
        return mock_full_chat
    mock_client.side_effect = slow_api_call

    # 并发启动 5 个请求
    start_time = time.time()
    tasks = [optimizer.get_chat_statistics(999) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    end_time = time.time()

    # 验证
    # 1. 结果应该都对
    for res in results:
        assert res['total_messages'] == 50
    
    # 2. get_entity 应该只被调用一次 (由于缓存和锁)
    # 注意：cached 装饰器会先查缓存。并发下，第一个请求拿走锁，第二个请求等待锁。
    # 第一个请求完成后写入缓存，第二个请求拿锁后 Double-Check 命中心。
    assert mock_client.get_entity.call_count == 1
    
    # 3. 耗时应该接近一次调用的耗时 (0.5s)，而不是 2.5s
    assert end_time - start_time < 1.0

@pytest.mark.asyncio
async def test_api_semaphore_limit(optimizer, mock_client):
    """验证信号量限制: 并发请求超过 10 个时，能够控制并发数 (逻辑验证)"""
    
    mock_entity = MagicMock(spec=Channel)
    mock_client.get_entity.return_value = mock_entity
    
    # 模拟无限个不同的 ID，绕过 Request Coalescing 的 key 锁
    # 这样可以测试信号量的并发限制
    active_calls = 0
    max_concurrent = 0

    async def tracked_api_call(*args, **kwargs):
        nonlocal active_calls, max_concurrent
        active_calls += 1
        max_concurrent = max(max_concurrent, active_calls)
        await asyncio.sleep(0.1)
        active_calls -= 1
        return MagicMock()

    mock_client.side_effect = tracked_api_call

    # 并发启动 15 个请求到 15 个不同的 ID
    tasks = [optimizer.get_chat_statistics(i) for i in range(15)]
    await asyncio.gather(*tasks)

    # 由于信号量设为 10，最大并发应该不超过 10
    assert max_concurrent <= 10
    assert max_concurrent > 0

@pytest.mark.asyncio
async def test_get_entity_timeout(optimizer, mock_client):
    """验证 get_entity 的硬超时保护"""
    
    async def forever_sleep(*args, **kwargs):
        await asyncio.sleep(100)
    
    mock_client.get_entity.side_effect = forever_sleep
    
    # 此时应该在 5 秒（我们设定的超时）后返回 {}
    start = time.time()
    result = await optimizer.get_chat_statistics(777)
    duration = time.time() - start
    
    assert result == {}
    assert 4.5 < duration < 6.0 # 考虑到系统误差，应该在 5s 左右
