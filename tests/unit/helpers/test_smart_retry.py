"""smart_retry 测试 — SmartRetryManager + @smart_retry 装饰器"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from core.helpers.smart_retry import SmartRetryManager, smart_retry


# Mock Telethon errors（不依赖 telethon）
class FakeFloodWaitError(Exception):
    def __init__(self, seconds=5):
        self.seconds = seconds
        super().__init__(f"FloodWait {seconds}s")

class FakeRPCError(Exception):
    def __init__(self, code=500):
        self.code = code
        super().__init__(f"RPC {code}")

class FakeServerInternalError(Exception):
    pass

class FakeConnectionError(Exception):
    pass


@pytest.fixture
def manager():
    return SmartRetryManager(max_retries=3, base_delay=0.01, max_delay=0.1)


class TestShouldRetry:
    """should_retry 判定逻辑"""

    def test_timeout_error_should_retry(self, manager):
        assert manager.should_retry(TimeoutError()) is True

    def test_connection_error_should_retry(self, manager):
        assert manager.should_retry(ConnectionError()) is True

    def test_unknown_error_should_not_retry(self, manager):
        assert manager.should_retry(ValueError("unknown")) is False

    def test_generic_exception_should_not_retry(self, manager):
        assert manager.should_retry(RuntimeError("oops")) is False


class TestExecute:
    """execute 重试执行测试"""

    @pytest.mark.asyncio
    async def test_success_no_retry(self, manager):
        """成功一次不重试"""
        func = AsyncMock(return_value="ok")
        result = await manager.execute(func)
        assert result == "ok"
        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, manager):
        """TimeoutError 触发重试，最终成功"""
        func = AsyncMock(side_effect=[TimeoutError(), TimeoutError(), "ok"])
        result = await manager.execute(func)
        assert result == "ok"
        assert func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, manager):
        """ConnectionError 触发重试"""
        func = AsyncMock(side_effect=[ConnectionError(), "ok"])
        result = await manager.execute(func)
        assert result == "ok"
        assert func.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_value_error(self, manager):
        """ValueError 不重试，直接抛出"""
        func = AsyncMock(side_effect=ValueError("bad"))
        with pytest.raises(ValueError, match="bad"):
            await manager.execute(func)
        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, manager):
        """超过最大重试次数后抛出最后一次异常"""
        func = AsyncMock(side_effect=TimeoutError())
        with pytest.raises(TimeoutError):
            await manager.execute(func)
        # 初始1次 + 3次重试 = 4次
        assert func.call_count == 4

    @pytest.mark.asyncio
    async def test_args_passed_through(self, manager):
        """参数正确传递"""
        func = AsyncMock(return_value="result")
        result = await manager.execute(func, "a", "b", key="val")
        assert result == "result"
        func.assert_called_once_with("a", "b", key="val")

    @pytest.mark.asyncio
    async def test_zero_retries_config(self):
        """max_retries=0 只执行一次"""
        mgr = SmartRetryManager(max_retries=0, base_delay=0.01)
        func = AsyncMock(side_effect=TimeoutError())
        with pytest.raises(TimeoutError):
            await mgr.execute(func)
        assert func.call_count == 1


class TestSmartRetryDecorator:
    """@smart_retry 装饰器测试"""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        @smart_retry(max_retries=2, base_delay=0.01)
        async def my_func():
            return "decorated"

        assert await my_func() == "decorated"

    @pytest.mark.asyncio
    async def test_decorator_retries(self):
        call_count = 0

        @smart_retry(max_retries=2, base_delay=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError()
            return "fixed"

        result = await flaky()
        assert result == "fixed"
        assert call_count == 3


class TestEdgeCases:
    """边界条件"""

    @pytest.mark.asyncio
    async def test_mixed_error_types(self, manager):
        """混合可重试和不可重试错误"""
        func = AsyncMock(side_effect=[TimeoutError(), ValueError("nope")])
        with pytest.raises(ValueError):
            await manager.execute(func)
        assert func.call_count == 2  # Timeout retry → ValueError stop

    @pytest.mark.asyncio
    async def test_success_after_single_failure(self, manager):
        """一次失败后成功"""
        func = AsyncMock(side_effect=[ConnectionError(), "ok"])
        assert await manager.execute(func) == "ok"
        assert func.call_count == 2
