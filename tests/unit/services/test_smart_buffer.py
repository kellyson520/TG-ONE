import unittest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from core.exceptions import TransientError
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
        task1 = asyncio.create_task(
            service.push(101, 201, ctx1, send_mock, **test_kwargs)
        )

        # 0.2s 后推入第二条 (重置防抖)
        await asyncio.sleep(0.2)
        ctx2 = MagicMock(message_id=2)
        task2 = asyncio.create_task(
            service.push(101, 201, ctx2, send_mock, **test_kwargs)
        )

        # 此时不应发送
        send_mock.assert_not_called()

        # 等待防抖时间过去 (0.5s)
        await asyncio.gather(task1, task2)

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
        tasks = []
        for i in range(3):
            tasks.append(
                asyncio.create_task(
                    service.push(
                        102,
                        202,
                        MagicMock(message_id=i),
                        send_mock,
                        **test_kwargs,
                    )
                )
            )
        await asyncio.gather(*tasks)

        send_mock.assert_called_once()
        self.assertEqual(len(send_mock.call_args[0][0]), 3)

    async def test_max_wait_time(self):
        service = SmartBufferService()
        send_mock = AsyncMock()
        test_kwargs = {"debounce_time": 2.0, "max_wait_time": 0.5}

        tasks = [
            asyncio.create_task(
                service.push(
                    103,
                    203,
                    MagicMock(message_id=1),
                    send_mock,
                    **test_kwargs,
                )
            )
        ]

        # 每隔 0.1s 推入新消息，防抖永远不会触发
        for i in range(4):
            await asyncio.sleep(0.1)
            tasks.append(
                asyncio.create_task(
                    service.push(
                        103,
                        203,
                        MagicMock(message_id=i + 2),
                        send_mock,
                        **test_kwargs,
                    )
                )
            )

        # 但因为总时间超过 0.5s，强行发车应该触发
        await asyncio.gather(*tasks)
        send_mock.assert_called()

    async def test_timer_exception_releases_context_pressure(self):
        service = SmartBufferService()
        key = (104, 204)
        service._buffers[key] = {
            "contexts": [MagicMock(message_id=1), MagicMock(message_id=2)],
            "last_received": time.time(),
            "start_time": time.time(),
            "config": {},  # Missing debounce/max_wait forces timer error path.
        }
        service._total_contexts = 2

        await service._wait_and_flush(key, AsyncMock())

        self.assertNotIn(key, service._buffers)
        self.assertEqual(service._total_contexts, 0)

    async def test_flush_re_raises_transient_failure_releases_pressure(self):
        service = SmartBufferService()
        key = (105, 205)
        service._buffers[key] = {
            "contexts": [MagicMock(message_id=1)],
            "last_received": time.time(),
            "start_time": time.time(),
            "config": {},
        }
        service._total_contexts = 1
        send_mock = AsyncMock(
            side_effect=TransientError("temporary network error")
        )

        with self.assertRaises(TransientError):
            await service._flush(key, send_mock)

        self.assertNotIn(key, service._buffers)
        self.assertEqual(service._total_contexts, 0)

    async def test_push_waits_for_timer_flush_and_propagates_failure(self):
        service = SmartBufferService()
        send_mock = AsyncMock(
            side_effect=TransientError("temporary send failure")
        )

        with self.assertRaises(TransientError):
            await service.push(
                106,
                206,
                MagicMock(message_id=1),
                send_mock,
                debounce_time=0.01,
                max_wait_time=0.05,
            )

        send_mock.assert_awaited_once()
        self.assertEqual(service._total_contexts, 0)

    async def test_timer_waits_without_polling_sleep(self):
        service = SmartBufferService()
        key = (107, 207)
        now = time.time()
        send_mock = AsyncMock()
        service._buffers[key] = {
            "contexts": [MagicMock(message_id=1)],
            "last_received": now,
            "start_time": now,
            "config": {
                "debounce": 0.01,
                "max_wait": 0.01,
                "max_batch": 10,
            },
            "event": asyncio.Event(),
        }
        service._total_contexts = 1
        sleep_calls = 0

        async def fake_sleep(delay):
            nonlocal sleep_calls
            sleep_calls += 1
            raise asyncio.CancelledError

        with patch("services.smart_buffer.asyncio.sleep", fake_sleep):
            await service._wait_and_flush(key, send_mock)

        self.assertEqual(sleep_calls, 0)
        send_mock.assert_awaited_once()

    async def test_timer_timeout_logs_before_deadline_flush(self):
        service = SmartBufferService()
        key = (108, 208)
        now = time.time()
        send_mock = AsyncMock()
        service._buffers[key] = {
            "contexts": [MagicMock(message_id=1)],
            "last_received": now,
            "start_time": now,
            "config": {
                "debounce": 0.01,
                "max_wait": 0.05,
                "max_batch": 10,
            },
            "event": asyncio.Event(),
        }
        service._total_contexts = 1

        with self.assertLogs("services.smart_buffer", level="DEBUG") as logs:
            await service._wait_and_flush(key, send_mock)

        self.assertTrue(
            any("缓冲区计时器等待超时" in message for message in logs.output)
        )
        send_mock.assert_awaited_once()

    async def test_timer_cancellation_logs_without_flushing(self):
        service = SmartBufferService()
        key = (109, 209)
        now = time.time()
        send_mock = AsyncMock()
        service._buffers[key] = {
            "contexts": [MagicMock(message_id=1)],
            "last_received": now,
            "start_time": now,
            "config": {
                "debounce": 1.0,
                "max_wait": 2.0,
                "max_batch": 10,
            },
            "event": asyncio.Event(),
        }
        service._total_contexts = 1

        async def fake_wait_for(awaitable, timeout):
            awaitable.close()
            raise asyncio.CancelledError

        with patch("services.smart_buffer.asyncio.wait_for", fake_wait_for):
            with self.assertLogs("services.smart_buffer", level="DEBUG") as logs:
                await service._wait_and_flush(key, send_mock)

        self.assertTrue(
            any("缓冲区计时器已取消" in message for message in logs.output)
        )
        send_mock.assert_not_awaited()
        self.assertIn(key, service._buffers)


if __name__ == "__main__":
    unittest.main()
