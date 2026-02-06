# 技术方案 (Spec) - 20260206_Hotfix_Four_Errors

## 1. 修复配置属性缺失 (Error 1)
- **目标**: 使得 `settings.HISTORY_MESSAGE_LIMIT` 可被访问。
- **改动位置**: `core/config/__init__.py` -> `Settings` 类。
- **实现细节**: 添加 `HISTORY_MESSAGE_LIMIT: int = Field(default=50, ...)`。

## 2. 修复 MessageContext 属性缺失 (Error 3)
- **目标**: 解决 `GlobalFilter` 尝试设置不存在的 `media_blocked` 属性的问题。
- **改动位置**: `filters/context.py` -> `MessageContext` 类。
- **实现细节**: 
    - 更新 `__slots__` 包含 `'media_blocked'`。
    - 在 `__init__` 中初始化 `self.media_blocked = False`。

## 3. 修复 MockEvent 缺失 Client (Error 4)
- **目标**: 防止在处理 MockEvent 时因缺失 `client` 属性而崩溃。
- **改动位置**: `filters/init_filter.py`。
- **实现细节**: 使用 `getattr(event, 'client', context.client)` 获取客户端实例。

## 4. 修复 SQLAlchemy Greenlet 错误 (Error 2)
- **目标**: 避免异步环境下访问已过期对象的属性触发隐式 I/O。
- **改动位置**: 
    - `core/database.py`: 设置 `expire_on_commit=False`。
    - `core/helpers/history/error_handler.py`: 确保 `session.rollback()` 被 `await`。
