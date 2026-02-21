# Bugfix Report: SQLite3 VACUUM Transaction Conflict

## Summary
修复了 `core.db_factory` 中 `VACUUM` 操作因在事务内执行而失败的问题。通过改用底层 DBAPI 连接并显式设置 `isolation_level = None` (AUTOCOMMIT)，成功绕过了 SQLAlchemy 的事务管理和事件监听器干扰。

## Root Cause Analysis
1.  **SQLAlchemy Event Listeners**: 在 `sqlite_config.py` 中注册了一个 `begin` 事件监听器，强制在每个事务开始时发送 `BEGIN IMMEDIATE`。即使使用了 `execution_options(isolation_level="AUTOCOMMIT")`，在某些情况下 SQLAlchemy 依然可能触发 `begin` 事件。
2.  **Transaction Management**: `VACUUM` 指令在 SQLite 中必须在事务块之外执行。SQLAlchemy 的高层 `Engine` 和 `Connection` 抽象有时会自动处理事务开始/结束，使得很难保证完全的 `AUTOCOMMIT` 状态。

## Implementation Details
1.  **`sqlite_config.py`**: 优化了 `do_begin_immediate` 监听器，增加判断：如果当前连接处于 `AUTOCOMMIT` 模式，则跳过 `BEGIN IMMEDIATE`。
2.  **`core/db_factory.py` (Sync)**: 使用 `engine.raw_connection()` 获取原始 DBAPI 连接，并设置 `raw_conn.isolation_level = None` 来执行 `VACUUM`。
3.  **`core/db_factory.py` (Async)**: 使用 `conn.run_sync()` 在 `aiosqlite` 内部线程中访问原始 `sqlite3.Connection`，同样设置 `isolation_level = None` 并执行 `VACUUM`。

## Verification Result
运行 `tests/reproduce_vacuum_bug.py` 测试：
- **Sync VACUUM**: Success (True)
- **Async VACUUM**: Success (True)
- **Logs**: 不再出现 `cannot VACUUM from within a transaction` 错误。

## Manual
该修复已集成到 `core/db_factory.py`，无需额外配置。所有的 `vacuum_database()` 和 `async_vacuum_database()` 调用现在都已安全。
