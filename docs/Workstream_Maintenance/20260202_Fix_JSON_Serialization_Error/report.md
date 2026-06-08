# 交付报告 (Report) - 修复 JSON 序列化失败

## 摘要 (Summary)
成功修复了系统在执行消息删除任务时抛出的 `TypeError: Object of type function is not JSON serializable` 错误。根本原因是 `async_delete_user_message` 尝试将一个局部定义的异步函数作为参数传递给持久化任务队列，而函数是不可 JSON 序列化的。

## 架构变更 (Architecture Refactor)
- **TaskService**: 增强了 `schedule_delete` 方法，使其支持直接传递 `chat_id` 和 `message_ids`，不再强制要求 `message` 对象。
- **WorkerService**: 在 Worker 核心处理逻辑中增加了对 `message_delete` 任务类型的原生支持，实现了任务的闭环处理。
- **Auto Delete Helper**: 将原有的基于回调的删除逻辑迁移为基于任务类型的持久化删除方案。

## 验证结果 (Verification)
- **静态检查**: 通过 `local-ci` 静态架构扫描和 Flake8 检查。
- **单元测试**: 
    - `tests/unit/services/test_task_service.py` 通过 (4 passed)。
    - `tests/unit/repositories/test_task_repo.py` 已修复并验证 (解决因 API 变更导致的 `fetch_next` 返回列表问题)。
- **回归测试**: 修复了 `message_listener.py` 中发现的缺失 `asyncio` 导入问题。

## 操作指南 (Manual)
- 如果需要增加新的异步延迟任务，建议优先使用已定义的任务类型（如 `message_delete`）。
- 如果必须使用 `schedule_custom_task`，请确保 `callback_info` 是纯字典且可 JSON 序列化。
