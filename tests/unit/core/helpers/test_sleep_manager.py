import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from core.helpers.sleep_manager import SleepManager


class TestSleepManager:
    @pytest.mark.asyncio
    async def test_sleep_wake_cycle(self):
        manager = SleepManager()
        manager.SLEEP_TIMEOUT = 0.1

        sleep_cb = MagicMock()
        wake_cb = MagicMock()

        manager.register_on_sleep(sleep_cb)
        manager.register_on_wake(wake_cb)

        manager.record_activity()
        assert not manager.is_sleeping

        await asyncio.sleep(0.2)

        if not manager.is_sleeping:
            if time.time() - manager._last_activity > manager.SLEEP_TIMEOUT:
                await manager._go_to_sleep()

        assert manager.is_sleeping
        sleep_cb.assert_called_once()

        manager.record_activity()
        assert not manager.is_sleeping
        wake_cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_already_sleeping(self):
        manager = SleepManager()
        manager._is_sleeping = True

        sleep_cb = MagicMock()
        manager.register_on_sleep(sleep_cb)

        await manager._go_to_sleep()
        sleep_cb.assert_not_called()

    @pytest.mark.asyncio
    async def test_monitor_cancellation(self):
        manager = SleepManager()

        async def fake_wait_for(awaitable, timeout):
            if hasattr(awaitable, "close"):
                awaitable.close()
            raise asyncio.CancelledError

        with patch("asyncio.wait_for", fake_wait_for):
            await manager.start_monitor()

    def test_stop_interface(self):
        manager = SleepManager()

        manager.stop()

    @pytest.mark.asyncio
    async def test_monitor_waits_until_idle_deadline(self, monkeypatch):
        manager = SleepManager()
        manager.SLEEP_TIMEOUT = 30.0
        manager._last_activity = 100.0
        wait_timeouts = []
        sleep_delays = []

        async def fake_wait_for(awaitable, timeout):
            wait_timeouts.append(timeout)
            if hasattr(awaitable, "close"):
                awaitable.close()
            raise asyncio.CancelledError

        async def fake_sleep(delay):
            sleep_delays.append(delay)
            raise asyncio.CancelledError

        monkeypatch.setattr(
            "core.helpers.sleep_manager.time.time",
            lambda: 100.0,
        )
        monkeypatch.setattr(
            "core.helpers.sleep_manager.asyncio.wait_for",
            fake_wait_for,
        )
        monkeypatch.setattr(
            "core.helpers.sleep_manager.asyncio.sleep",
            fake_sleep,
        )

        await manager.start_monitor()

        assert sleep_delays == []
        assert wait_timeouts == [pytest.approx(30.0)]

    @pytest.mark.asyncio
    async def test_monitor_timeout_is_observable(self, monkeypatch, caplog):
        manager = SleepManager()
        manager.SLEEP_TIMEOUT = 30.0
        manager._last_activity = 100.0

        async def fake_wait_for(awaitable, timeout):
            if hasattr(awaitable, "close"):
                awaitable.close()
            manager._running = False
            raise asyncio.TimeoutError

        monkeypatch.setattr(
            "core.helpers.sleep_manager.time.time",
            lambda: 100.0,
        )
        monkeypatch.setattr(
            "core.helpers.sleep_manager.asyncio.wait_for",
            fake_wait_for,
        )
        caplog.set_level("DEBUG", logger="core.helpers.sleep_manager")

        await manager.start_monitor()

        assert "SleepManager: Idle wait timed out" in caplog.text

    @pytest.mark.asyncio
    async def test_stop_wakes_monitor(self):
        manager = SleepManager()
        manager.SLEEP_TIMEOUT = 60.0

        task = asyncio.create_task(manager.start_monitor())
        await asyncio.sleep(0)

        manager.stop()
        await asyncio.sleep(0)

        try:
            assert task.done()
        finally:
            if not task.done():
                task.cancel()
                await task
