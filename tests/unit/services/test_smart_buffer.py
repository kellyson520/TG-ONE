import unittest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from services.smart_buffer import SmartBufferService

class TestSmartBuffer(unittest.IsolatedAsyncioTestCase):
    async def test_debounce_and_flush(self):
        # 初始化服务
        service = SmartBufferService()
        send_mock = AsyncMock()
        
        # 配置参数
        test_kwargs = {"debounce_time": 0.5, "max_wait_time": 1.0}
        
        # 1. 推入第一条
        ctx1 = MagicMock(message_id=1)
        await service.push(101, 201, ctx1, send_mock, **test_kwargs)
        
        # 0.2s 后推入第二条 (重置防抖)
        await asyncio.sleep(0.2)
        ctx2 = MagicMock(message_id=2)
        await service.push(101, 201, ctx2, send_mock, **test_kwargs)
        
        # 此时不应发送
        send_mock.assert_not_called()
        
        # 等待防抖时间过去 (0.5s)
        await asyncio.sleep(0.6)
        
        # 应该被调用一次，携带两条消息
        send_mock.assert_called_once()
        buffered_ctxs = send_mock.call_args[0][0]
        self.assertEqual(len(buffered_ctxs), 2)
        self.assertEqual(buffered_ctxs[0].message_id, 1)

    async def test_max_batch_size(self):
        service = SmartBufferService()
        send_mock = AsyncMock()
        test_kwargs = {"max_batch_size": 3}
        
        # 连续推入 3 条，应立即触发
        for i in range(3):
            await service.push(102, 202, MagicMock(message_id=i), send_mock, **test_kwargs)
            
        send_mock.assert_called_once()
        self.assertEqual(len(send_mock.call_args[0][0]), 3)

    async def test_max_wait_time(self):
        service = SmartBufferService()
        send_mock = AsyncMock()
        test_kwargs = {"debounce_time": 2.0, "max_wait_time": 0.5}
        
        await service.push(103, 203, MagicMock(message_id=1), send_mock, **test_kwargs)
        
        # 每隔 0.1s 推入新消息，防抖永远不会触发
        for i in range(4):
            await asyncio.sleep(0.1)
            await service.push(103, 203, MagicMock(message_id=i+2), send_mock, **test_kwargs)
            
        # 但因为总时间超过 0.5s，强行发车应该触发
        await asyncio.sleep(0.4)
        send_mock.assert_called()

if __name__ == "__main__":
    unittest.main()
