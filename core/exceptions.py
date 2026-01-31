class TFError(Exception):
    """系统基础异常类"""
    def __init__(self, message: str, context: dict | None = None) -> None:
        super().__init__(message)
        self.context = context or {}

class TransientError(TFError):
    """
    瞬态错误（可自动重试）
    场景：网络超时、API 限流 (429)、数据库锁、临时服务不可用
    """
    pass

class PermanentError(TFError):
    """
    永久错误（不可重试，应直接标记失败）
    场景：数据校验失败、文件不存在、权限不足、配置错误
    """
    pass

class BusinessLogicError(PermanentError):
    """业务逻辑错误，如规则匹配失败等"""
    pass
