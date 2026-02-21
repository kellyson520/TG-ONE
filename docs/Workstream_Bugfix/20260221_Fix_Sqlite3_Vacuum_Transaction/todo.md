# Fix SQLite3 VACUUM Transaction Bug

## Context
用户报告 `core.db_factory` 中的 `VACUUM` 失败，提示 `cannot VACUUM from within a transaction`。这通常是因为 SQLAlchemy 的连接默认在事务中运行，或者 `execution_options(isolation_level="AUTOCOMMIT")` 未能正确生效以致无法执行 `VACUUM` 指令。

## Strategy
1. 分析 `core/db_factory.py` 中的 `vacuum_database` 和 `async_vacuum_database` 实现。
2. 确保在执行 `VACUUM` 之前没有活跃的事务。
3. 对于异步情况，确保 `isolation_level="AUTOCOMMIT"` 能够正确应用，或者手动关闭事务。
4. 验证修复效果。

## Checklist

### Phase 1: Implementation Fix
- [x] 优化同步 `vacuum_database` 函数，确保真正的 AUTOCOMMIT 模式。
- [x] 优化异步 `async_vacuum_database` 函数，确保真正的 AUTOCOMMIT 模式。
- [x] 检查 `core/helpers/sqlite_config.py` 是否有干扰 `VACUUM` 的 `begin` 监听器。 (已修复)

### Phase 2: Verification
- [x] 编写测试脚本触发 `VACUUM`。
- [x] 检查日志确保不再报错。
