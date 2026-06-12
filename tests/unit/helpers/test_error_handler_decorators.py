"""error_handler 测试 — 统一错误处理装饰器"""
import pytest
import asyncio
import logging
from unittest.mock import MagicMock
from core.helpers.error_handler import (
    handle_errors,
    retry_on_failure,
    log_execution,
)


class TestHandleErrors:
    """handle_errors 装饰器测试"""

    @pytest.mark.asyncio
    async def test_async_success(self):
        @handle_errors(default_return="fallback")
        async def ok():
            return "success"

        assert await ok() == "success"

    @pytest.mark.asyncio
    async def test_async_exception_returns_default(self):
        @handle_errors(default_return="fallback")
        async def fail():
            raise ValueError("boom")

        assert await fail() == "fallback"

    def test_sync_success(self):
        @handle_errors(default_return="fallback")
        def ok():
            return "success"

        assert ok() == "success"

    def test_sync_exception_returns_default(self):
        @handle_errors(default_return=None)
        def fail():
            raise RuntimeError("boom")

        assert fail() is None

    def test_sync_reraise(self):
        @handle_errors(reraise=True)
        def fail():
            raise ValueError("reraise me")

        with pytest.raises(ValueError, match="reraise me"):
            fail()

    @pytest.mark.asyncio
    async def test_async_reraise(self):
        @handle_errors(reraise=True)
        async def fail():
            raise ValueError("reraise me")

        with pytest.raises(ValueError, match="reraise me"):
            await fail()

    def test_specific_errors_caught(self):
        """只捕获特定异常类型"""
        @handle_errors(default_return="caught", specific_errors=ValueError)
        def fail():
            raise ValueError("specific")

        assert fail() == "caught"

    def test_specific_errors_let_others_pass(self):
        """非指定异常不捕获"""
        @handle_errors(default_return="caught", specific_errors=ValueError)
        def fail():
            raise RuntimeError("not caught")

        with pytest.raises(RuntimeError):
            fail()

    def test_default_return_none(self):
        """默认 default_return=None"""
        @handle_errors()
        def fail():
            raise ValueError()

        assert fail() is None

    def test_preserves_function_name(self):
        @handle_errors()
        def my_func():
            pass

        assert my_func.__name__ == "my_func"


class TestRetryOnFailure:
    """retry_on_failure 装饰器测试"""

    @pytest.mark.asyncio
    async def test_async_success_first_try(self):
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01)
        async def ok():
            nonlocal call_count
            call_count += 1
            return "done"

        assert await ok() == "done"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retries_then_succeeds(self):
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("not yet")
            return "ok"

        assert await flaky() == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_max_retries_exceeded(self):
        call_count = 0

        @retry_on_failure(max_retries=2, delay=0.01)
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            await always_fail()
        assert call_count == 2

    def test_sync_retries_then_succeeds(self):
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("nope")
            return "ok"

        assert flaky() == "ok"
        assert call_count == 2

    def test_sync_max_retries_exceeded(self):
        call_count = 0

        @retry_on_failure(max_retries=2, delay=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("broken")

        with pytest.raises(RuntimeError):
            always_fail()
        assert call_count == 2

    def test_specific_exceptions_only(self):
        """只重试指定异常"""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01, exceptions=ValueError)
        def wrong_error():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("not value error")

        with pytest.raises(RuntimeError):
            wrong_error()
        assert call_count == 1  # 不重试

    @pytest.mark.asyncio
    async def test_preserves_name(self):
        @retry_on_failure(max_retries=1, delay=0.01)
        async def named_func():
            pass

        assert named_func.__name__ == "named_func"


class TestLogExecution:
    """log_execution 装饰器测试"""

    @pytest.mark.asyncio
    async def test_async_logs_execution(self, caplog):
        @log_execution(level=logging.INFO)
        async def tracked():
            return 42

        with caplog.at_level(logging.INFO):
            result = await tracked()

        assert result == 42
        assert any("tracked" in r.message for r in caplog.records)

    def test_sync_logs_execution(self, caplog):
        @log_execution(level=logging.INFO)
        def tracked():
            return "result"

        with caplog.at_level(logging.INFO):
            result = tracked()

        assert result == "result"
        assert any("tracked" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_args_when_enabled(self, caplog):
        @log_execution(include_args=True, level=logging.DEBUG)
        async def with_args(x, y):
            return x + y

        with caplog.at_level(logging.DEBUG):
            await with_args(1, 2)

        assert any("1" in r.message and "2" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_result_when_enabled(self, caplog):
        @log_execution(include_result=True, level=logging.DEBUG)
        async def returns_value():
            return "important"

        with caplog.at_level(logging.DEBUG):
            await returns_value()

        assert any("important" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_exception(self, caplog):
        @log_execution(level=logging.ERROR)
        async def will_fail():
            raise ValueError("test error")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                await will_fail()

        assert any("异常" in r.message or "error" in r.message.lower() for r in caplog.records)
