"""
错误处理器
提供智能重试和错误分类功能
"""
import asyncio
import logging
from typing import Callable, Any, Optional, Tuple
from functools import wraps

logger = logging.getLogger(__name__)

# 可重试的错误类型
RETRYABLE_ERRORS = {
    "FloodWaitError",  # Telegram频率限制
    "TimeoutError",  # 超时
    "ConnectionError",  # 连接错误
    "ServerError",  # 服务器错误
    "SlowModeWaitError",  # 慢速模式
}

# 不可重试的错误类型
NON_RETRYABLE_ERRORS = {
    "ChatAdminRequiredError",  # 需要管理员权限
    "ChatWriteForbiddenError",  # 禁止写入
    "MessageIdInvalidError",  # 消息ID无效
    "UserBannedInChannelError",  # 用户被封禁
    "ChannelPrivateError",  # 频道私有
}


class ErrorHandler:
    """错误处理器 - 提供智能重试和错误分类"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """
        初始化错误处理器

        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟时间(秒)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay

        # 统计信息
        self.total_retries = 0
        self.total_failures = 0
        self.error_counts = {}

    def is_retryable(self, error: Exception) -> bool:
        """
        判断错误是否可重试

        Args:
            error: 异常对象

        Returns:
            bool: True=可重试, False=不可重试
        """
        error_name = type(error).__name__

        # 检查是否在不可重试列表中
        if error_name in NON_RETRYABLE_ERRORS:
            return False

        # 检查是否在可重试列表中
        if error_name in RETRYABLE_ERRORS:
            return True

        # 默认不重试未知错误
        return False

    async def retry_with_backoff(
        self,
        func: Callable,
        *args,
        context: Optional[dict] = None,
        **kwargs,
    ) -> Tuple[bool, Any]:
        """
        使用指数退避重试函数

        Args:
            func: 要执行的异步函数
            *args: 位置参数
            context: 上下文信息(用于日志)
            **kwargs: 关键字参数

        Returns:
            Tuple[bool, Any]: (成功标志, 返回值或错误)
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                result = await func(*args, **kwargs)
                return True, result

            except Exception as e:
                last_error = e
                error_name = type(e).__name__

                # 记录错误统计
                self.error_counts[error_name] = (
                    self.error_counts.get(error_name, 0) + 1
                )

                # 判断是否可重试
                if not self.is_retryable(e):
                    logger.error(
                        f"❌ 不可重试错误: {error_name} - {str(e)}",
                        extra={"context": context or {}},
                    )
                    self.total_failures += 1
                    return False, e

                # 最后一次尝试失败
                if attempt == self.max_retries - 1:
                    logger.error(
                        f"❌ 重试{self.max_retries}次后仍失败: {error_name} - {str(e)}",
                        extra={"context": context or {}},
                    )
                    self.total_failures += 1
                    return False, e

                # 计算等待时间(指数退避)
                wait_time = self._calculate_backoff_time(attempt, e)

                logger.warning(
                    f"⚠️ 第{attempt + 1}次尝试失败: {error_name}, "
                    f"{wait_time}秒后重试... ({str(e)})",
                    extra={"context": context or {}},
                )

                self.total_retries += 1
                await asyncio.sleep(wait_time)

        return False, last_error

    def _calculate_backoff_time(self, attempt: int, error: Exception) -> float:
        """
        计算退避时间

        Args:
            attempt: 当前尝试次数(从0开始)
            error: 异常对象

        Returns:
            float: 等待时间(秒)
        """
        # 基础指数退避: 1s, 2s, 4s, 8s...
        base_wait = self.base_delay * (2**attempt)

        # 特殊处理 FloodWaitError
        error_name = type(error).__name__
        if error_name == "FloodWaitError":
            # Telegram会告知需要等待的秒数
            if hasattr(error, "seconds"):
                return float(error.seconds)

        return base_wait

    def log_error(
        self,
        error: Exception,
        context: Optional[dict] = None,
        level: str = "error",
    ):
        """
        记录详细错误日志

        Args:
            error: 异常对象
            context: 上下文信息
            level: 日志级别
        """
        error_name = type(error).__name__
        error_msg = str(error)

        log_data = {
            "error_type": error_name,
            "error_message": error_msg,
            "is_retryable": self.is_retryable(error),
        }

        if context:
            log_data.update(context)

        log_func = getattr(logger, level, logger.error)
        log_func(f"错误详情: {error_name} - {error_msg}", extra=log_data)

    def get_statistics(self) -> dict:
        """获取错误统计信息"""
        return {
            "total_retries": self.total_retries,
            "total_failures": self.total_failures,
            "error_counts": self.error_counts.copy(),
            "most_common_error": (
                max(self.error_counts.items(), key=lambda x: x[1])[0]
                if self.error_counts
                else None
            ),
        }

    def reset_statistics(self):
        """重置统计信息"""
        self.total_retries = 0
        self.total_failures = 0
        self.error_counts.clear()


# 装饰器版本
def retry_on_error(max_retries: int = 3, base_delay: float = 1.0):
    """
    重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间

    Example:
        @retry_on_error(max_retries=3)
        async def fetch_message(chat_id, message_id):
            return await client.get_messages(chat_id, ids=message_id)
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            handler = ErrorHandler(max_retries, base_delay)
            success, result = await handler.retry_with_backoff(func, *args, **kwargs)
            if not success:
                raise result  # 重新抛出最后的错误
            return result

        return wrapper

    return decorator
