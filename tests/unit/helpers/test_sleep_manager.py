"""sleep_manager 测试 — 闲置检测与睡眠模式"""
import pytest
import asyncio
import time
from unittest.mock import MagicMock
from core.helpers.sleep_manager import SleepManager


@pytest.fixture
def sm():
    """短超时的 SleepManager"""
    mgr = SleepManager()
    mgr.SLEEP_TIMEOUT = 0.5  # 0.5秒超时，测试快
    return mgr


class TestSleepManagerBasic:
    """基本属性测试"""

    def test_initial_not_sleeping(self, sm):
        assert sm.is_sleeping is False

    def test_initial_not_running(self, sm):
        assert sm._running is False

    def test_record_activity_updates_time(self, sm):
        old_time = sm._last_activity
        time.sleep(0.01)
        sm.record_activity()
        assert sm._last_activity > old_time


class TestSleepCallbacks:
    """回调注册与触发"""

    def test_register_on_sleep(self, sm):
        cb = MagicMock()
        sm.register_on_sleep(cb)
        assert cb in sm._on_sleep_callbacks

    def test_register_on_wake(self, sm):
        cb = MagicMock()
        sm.register_on_wake(cb)
        assert cb in sm._on_wake_callbacks


class TestSleepWakeup:
    """睡眠/唤醒状态转换"""

    @pytest.mark.asyncio
    async def test_sleeps_after_timeout(self, sm):
        """超时后进入睡眠"""
        sm.SLEEP_TIMEOUT = 0.3
        await sm._go_to_sleep()
        assert sm.is_sleeping is True

    @pytest.mark.asyncio
    async def test_wake_on_activity(self, sm):
        """活动唤醒"""
        await sm._go_to_sleep()
        assert sm.is_sleeping is True
        sm.record_activity()
        assert sm.is_sleeping is False

    @pytest.mark.asyncio
    async def test_sleep_callback_triggered(self, sm):
        """睡眠回调触发"""
        cb = MagicMock()
        sm.register_on_sleep(cb)
        await sm._go_to_sleep()
        cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_wake_callback_triggered(self, sm):
        """唤醒回调触发"""
        cb = MagicMock()
        sm.register_on_wake(cb)
        await sm._go_to_sleep()
        sm.record_activity()
        cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_double_sleep_no_duplicate(self, sm):
        """重复睡眠不会重复触发"""
        cb = MagicMock()
        sm.register_on_sleep(cb)
        await sm._go_to_sleep()
        await sm._go_to_sleep()
        cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_exception_handled(self, sm):
        """回调异常不影响其他回调"""
        bad_cb = MagicMock(side_effect=RuntimeError("boom"))
        good_cb = MagicMock()
        sm.register_on_sleep(bad_cb)
        sm.register_on_sleep(good_cb)
        await sm._go_to_sleep()
        good_cb.assert_called_once()


class TestTimeUntilSleep:
    """_time_until_sleep 计算"""

    def test_fresh_activity_returns_timeout(self, sm):
        sm.SLEEP_TIMEOUT = 5.0
        remaining = sm._time_until_sleep()
        assert 4.0 < remaining <= 5.0

    def test_after_delay_returns_less(self, sm):
        sm.SLEEP_TIMEOUT = 5.0
        sm._last_activity = time.time() - 3.0
        remaining = sm._time_until_sleep()
        assert 1.5 < remaining < 2.5

    def test_expired_returns_zero(self, sm):
        sm.SLEEP_TIMEOUT = 1.0
        sm._last_activity = time.time() - 5.0
        remaining = sm._time_until_sleep()
        assert remaining == 0.0


class TestMonitorLifecycle:
    """start/stop 生命周期"""

    @pytest.mark.asyncio
    async def test_start_sets_running(self, sm):
        task = asyncio.create_task(sm.start_monitor())
        await asyncio.sleep(0.1)
        assert sm._running is True
        sm.stop()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_stop_clears_running(self, sm):
        task = asyncio.create_task(sm.start_monitor())
        await asyncio.sleep(0.1)
        sm.stop()
        await asyncio.sleep(0.1)
        assert sm._running is False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_double_start_ignored(self, sm):
        task1 = asyncio.create_task(sm.start_monitor())
        await asyncio.sleep(0.1)
        # 第二次 start 应该被忽略
        await sm.start_monitor()
        sm.stop()
        await asyncio.sleep(0.1)
        task1.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_activity_during_monitor(self, sm):
        """监控期间活动不会导致睡眠"""
        sm.SLEEP_TIMEOUT = 0.3
        task = asyncio.create_task(sm.start_monitor())
        # 持续发送活动信号
        for _ in range(5):
            sm.record_activity()
            await asyncio.sleep(0.1)
        assert sm.is_sleeping is False
        sm.stop()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_wake_during_sleep(self, sm):
        """睡眠期间唤醒恢复监控"""
        sm.SLEEP_TIMEOUT = 0.2
        task = asyncio.create_task(sm.start_monitor())
        await asyncio.sleep(0.3)
        assert sm.is_sleeping is True
        sm.record_activity()
        await asyncio.sleep(0.1)
        assert sm.is_sleeping is False
        sm.stop()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
