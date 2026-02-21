# 任务交付报告: 修复 AdminLogs 缺失与 Invalid Message ID 错误

## 摘要 (Summary)
成功修复了后台菜单日志面板的调用错误，消除了未匹配动作的冗余日志，并增强了转发队列对 Telegram 终端错误（如无效消息 ID）的防御机制。

## 架构变更 (Architecture Refactor)
- **MenuController (Facade)**: 增加了 `show_admin_logs` 方法作为别名，对齐了 `AdminMenuStrategy` 的预期接口，确保了 UI 动作与后端逻辑的连通性。
- **Registry Strategy Pattern**: 优化了 `MenuHandlerRegistry.dispatch` 逻辑。现在 `matched=True` 标志在 `handle` 调用之前设置，这样即使 handler 内部报错，也不会再误报 "Unmatched Action"，使得错误日志更加精准。
- **Queue Service (Terminal Error Handling)**: 在 `TelegramQueueService` 的重试循环中引入了终端错误识别。对于 `MessageIdInvalidError` 等 400 错误，直接向上抛出并跳过重试，避免了无限无效重试造成的资源浪费和日志泛滥。

## 验证结果 (Verification)
- **单元测试**:
    - `tests/unit/handlers/button/strategies/test_registry_monitoring.py` 通过：验证了注册器统计逻辑。
    - `tests/test_qos_v4.py` 通过：验证了队列服务的核心稳定性。
- **手动审计**:
    - 确认 `MenuController.show_admin_logs` 已正确导出。
    - 确认 `queue_service.py` 已包含对 Telethon 终端错误的导入与处理。

## 关键修复点
1. **AttributeError**: `MenuController` 补全了 `show_admin_logs` 接口。
2. **Unmatched Warning**: 修改了 `registry.py` 的匹配逻辑，优先标记匹配状态再执行处理。
3. **Invalid Message ID**: 在转发底层增加了针对无效 ID 的直跳逻辑，防止无效重试。
