# 任务报告: 修复转发详细统计显示异常 (Report: Forward Stats Fix)

## 任务概览 (Summary)
本次任务修复了“转发详细统计”面板中周期显示为问号、内容类型分布显示为 "Unknown" 以及数据不一致的问题。通过优化 `AdminController` 的调用逻辑和重构 `AnalyticsService` 的数据聚合方法，确保了数据的完整性和准确性，解决了 DuckDB 与 SQLite 的锁冲突问题。

## 架构调整 (Architecture Refactor)
- **Controller**: `AdminController` 切换为调用 `get_detailed_analytics`，该方法现已正确封装 `period`, `summary`, `daily_stats`, `type_distribution` 等字段。
- **Service**:
  - `AnalyticsService.get_detailed_analytics`: 移除外层事务锁 (Session)，避免与内部 `UnifiedQueryBridge` (DuckDB) 的 SQLite 读取冲突导致死锁。
  - `AnalyticsService.get_detailed_stats`: 
    - 修复了 `Top Chats` 查询逻辑，改为查询 `chat_statistics` 表 (SQLite/Archive) 而非不存在的 `rule_logs.source_chat_id`。
    - 优化了 `Top Rules` 和 `Type Distribution` 的聚合逻辑，支持跨天范围查询。
    - 修复了内容类型 "Unknown" 问题，增加了对 `message_type` 字段的 `None` 值回退处理 (默认为 "text")。

## 验证结果 (Verification)
- **模拟测试**: 编写 `test_analytics.py` 进行模拟调用，确认 `get_detailed_analytics` 返回的数据结构完整，包含正确的 `period` (days=7) 和非空的 `type_distribution`。
- **并发安全**: 验证了在无外层 Session 锁的情况下，DuckDB (`bridge`) 可以正常读取运行中的 SQLite 数据库而不发生死锁。
- **数据准确**: 确认 `daily_stats` 包含查询当天的实时数据。

## 关键代码变更 (Key Changes)
- `services/analytics_service.py`:
  - `get_detailed_analytics`: Removed `async with get_session()` context manager.
  - `get_detailed_stats`: Updated SQL queries for `chat_statistics` and date ranges.
  - `get_detailed_stats`: Fixed `message_type` normalization (`m_type_raw = r['message_type'] or "text"`).

## 后续建议 (Recommendations)
- 建议在 UI 层面增加 `Top Chats` 的展示，目前数据已就绪但未渲染。
- 持续监控 `UnifiedQueryBridge` 在高并发下的性能表现。
