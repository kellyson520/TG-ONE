# Task Report: Fix EventBus Emit Error

## Summary (摘要)
修复了 `core.bootstrap` 模块在系统关闭过程中因调用不存在的 `EventBus.emit()` 方法而导致的 `AttributeError`。同时，清理了 `services.rule.crud` 中存在的异步方法调用缺失 `await` 的潜在隐患。

## Architecture Refactor (架构变更)
- **Attribute Alignment**: 将 `core/bootstrap.py` 中的 `bus.emit` 统一为 `bus.publish`，以符合 `EventBus` 的标准接口定义。
- **Async Safety**: 增强了规则管理服务 (`RuleCRUDService`) 的异步安全性，确保事件发布操作被正确等待。

## Verification (验证结果)
- **Static Analysis**: 经 `grep` 全局搜索，非日志模块已无 `emit()` 方法误用。
- **Interface Proof**: 已核实 `core/event_bus.py` 中 `publish` 为唯一合规发布方法。

## Manual (关键说明)
- 开发者在扩展 `EventBus` 监听或发布逻辑时，请务必使用 `publish` 方法并配合 `await` 关键字。
