# 任务报告: SQLite 数据库锁定深度治理

## 1. 任务背景
在高并发场景下，SQLite 经常出现 `database is locked` 错误。之前虽然启用了 WAL 模式，但由于事务升级机制（Shared -> Reserved -> Exclusive）在多连接并发写时容易冲突，导致锁升级失败。

## 2. 核心修复措施

### 2.1 引入 `BEGIN IMMEDIATE` 模式
通过 SQLAlchemy 事件监听器，在每个事务开始时强制执行 `BEGIN IMMEDIATE`。
- **效果**: 事务在启动时即尝试获取写锁（Reserved Lock），如果失败则在 `busy_timeout` 内排队。这避免了多个连接同时持有读锁并尝试升级为写锁导致的死锁。

### 2.2 统一连接配置
创建了 `core/helpers/sqlite_config.py`，统一了以下配置并应用于所有数据库引擎（Database 类及 DbFactory）：
- **WAL 模式**: 允许并发读写。
- **Busy Timeout**: 增加到 30s。
- **Synchronous**: 设置为 NORMAL 以提升写入性能。
- **Cache Size**: 设置为 64MB。
- **Temp Store**: 设置为 MEMORY。

### 2.3 仓库层逻辑加固
- **统一重试装饰器**: `TaskRepository` 的所有关键写入和拉取路径（`fetch_next`, `push_batch`, `fetch_group_tasks`）现在均受 `@async_db_retry` 保护。
- **重试日志增强**: 重试日志现在包含完整的方法路径和名称，方便定位热点冲突路径。

## 3. 验证结果
- **配置验证**: 经 `tests/temp/verify_db_pragma.py` 验证，PRAGMA 参数已正确应用。
- **日志验证**: 通过 DEBUG 日志确认 `BEGIN IMMEDIATE` 已成功应用于事务启动。
- **稳定性**: 统一配置减少了不同模块间连接行为的不一致性，降低了锁竞争机率。

## 4. 架构影响
- 读写连接行为更加明确：读连接不启用 `BEGIN IMMEDIATE`，写连接强制启用。
- 依赖于 `core/helpers/sqlite_config.py` 进行引擎初始化。

## 5. 后续建议
- 如果系统负载继续增长导致 I/O 等待时间过长，建议迁移至共享数据库（如 PostgreSQL）。
- 保持对 `[DB_RETRY]` 日志的关注，如果某个方法频繁触发重试，说明该处存在极高的写入竞争。
