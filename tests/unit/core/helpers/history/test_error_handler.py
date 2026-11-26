import pytest
import asyncio
from core.helpers.history.error_handler import ErrorHandler


class FloodWaitError(Exception):
    seconds = 42


class ChatAdminRequiredError(Exception):
    pass


class TestIsRetryable:
    def setup_method(self):
        self.handler = ErrorHandler(max_retries=3, base_delay=1.0)

    def test_timeout_is_retryable(self):
        assert self.handler.is_retryable(TimeoutError()) is True

    def test_connection_error_is_retryable(self):
        assert self.handler.is_retryable(ConnectionError()) is True

    def test_unknown_error_not_retryable(self):
        assert self.handler.is_retryable(ValueError("unknown")) is False

    def test_keyboard_interrupt_not_retryable(self):
        assert self.handler.is_retryable(KeyboardInterrupt()) is False


class TestBackoffCalculation:
    def setup_method(self):
        self.handler = ErrorHandler(max_retries=5, base_delay=2.0)

    def test_first_attempt(self):
        delay = self.handler._calculate_backoff_time(0, TimeoutError())
        assert delay == 2.0

    def test_second_attempt(self):
        delay = self.handler._calculate_backoff_time(1, TimeoutError())
        assert delay == 4.0

    def test_exponential_growth(self):
        delay = self.handler._calculate_backoff_time(3, TimeoutError())
        assert delay == 16.0

    def test_flood_wait_uses_error_seconds(self):
        delay = self.handler._calculate_backoff_time(0, FloodWaitError())
        assert delay == 42.0


class TestStatistics:
    def setup_method(self):
        self.handler = ErrorHandler()

    def test_initial_stats(self):
        stats = self.handler.get_statistics()
        assert stats["total_retries"] == 0
        assert stats["total_failures"] == 0

    def test_stats_after_increment(self):
        self.handler.total_retries = 5
        self.handler.total_failures = 2
        stats = self.handler.get_statistics()
        assert stats["total_retries"] == 5
        assert stats["total_failures"] == 2

    def test_reset(self):
        self.handler.total_retries = 10
        self.handler.total_failures = 3
        self.handler.error_counts["TimeoutError"] = 7
        self.handler.reset_statistics()
        stats = self.handler.get_statistics()
        assert stats["total_retries"] == 0
        assert stats["total_failures"] == 0


class TestRetryWithBackoff:
    def setup_method(self):
        self.handler = ErrorHandler(max_retries=3, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        call_count = 0
        async def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"
        success, result = await self.handler.retry_with_backoff(succeed)
        assert success is True
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_timeout_then_succeed(self):
        call_count = 0
        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "recovered"
        success, result = await self.handler.retry_with_backoff(fail_twice)
        assert success is True
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhaust_retries_returns_false(self):
        async def always_fail():
            raise TimeoutError("always")
        success, error = await self.handler.retry_with_backoff(always_fail)
        assert success is False
        assert isinstance(error, TimeoutError)
        assert self.handler.total_failures == 1

    @pytest.mark.asyncio
    async def test_non_retryable_returns_immediately(self):
        call_count = 0
        async def forbidden():
            nonlocal call_count
            call_count += 1
            raise ChatAdminRequiredError("no perms")
        success, error = await self.handler.retry_with_backoff(forbidden)
        assert success is False
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_counter_increments(self):
        call_count = 0
        async def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("once")
            return "ok"
        await self.handler.retry_with_backoff(fail_once)
        assert self.handler.total_retries == 1

    @pytest.mark.asyncio
    async def test_error_counts_tracked(self):
        async def always_fail():
            raise TimeoutError("track")
        await self.handler.retry_with_backoff(always_fail)
        assert "TimeoutError" in self.handler.error_counts
