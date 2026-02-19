# Fix DuckDB Timestamp Cast Error

## 背景 (Context)
在 `UnifiedQueryBridge` 执行跨热冷聚合查询时，DuckDB 抛出 `Binder Error: Cannot compare values of type TIMESTAMP and type VARCHAR - an explicit cast is required`。
这是因为 `rule_logs` 表的 `created_at` 字段在 Parquet 中是 `TIMESTAMP` 类型，而传入的过滤参数是 `VARCHAR`（字符串），DuckDB 不会自动隐式转换。

## 待办清单 (Checklist)

### Phase 1: 问题诊断与修复
- [x] 定位问题代码：`services/analytics_service.py` 中的 `get_unified_hourly_trend`。
- [x] 修复代码：在 `WHERE` 子句中添加显式类型转换 `CAST(? AS TIMESTAMP)`。
- [x] 检查其他类似的查询（如 `get_daily_summary`, `get_detailed_stats`）确保一致性。

### Phase 2: 验证
- [x] 验证 `detailed_analytics` 功能。

### Phase 3: 归档
- [x] 提交修改。
- [x] 编写 `report.md`。
- [x] 更新 `process.md`。
