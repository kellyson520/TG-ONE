# 任务报告: 修复 SQLite 数据库锁定错误 (TaskQueue 更新失败)

## 1. 任务概述
- **任务ID**: 20260218_Fix_SQLite_Locked_TaskQueue
- **类型**: 数据库优化 / 缺陷修复
- **目标**: 解决在高并发消息处理场景下，`task_queue` 表更新操作频繁触发 `database is locked` 的问题。

## 2. 核心变更

### 2.1 SQLite 配置升级 (`PRAGMA`)
在 `core/database.py` 和 `core/db_factory.py` 中对 SQLite 连接进行了深度调优：
- **busy_timeout**: 从 5s 增加到 **30s**，给予并发事务更充足的等待缓冲。
- **journal_mode**: 强制开启 **WAL (Write-Ahead Logging)**，允许多个读操作和一个写操作并发进行。
- **synchronous**: 设置为 **NORMAL**，在保证基本安全的前提下大幅提升写入性能。
- **journal_size_limit**: 限制为 **20MB**，防止 WAL 文件无限增长占用空间。
- **cache_size**: 设置为 **64MB** (-64000)，增加内存缓存以减少磁盘 I/O。
- **temp_store**: 设置为 **MEMORY**，临时表在内存中处理。

### 2.2 异步重试机制
新建 `core/helpers/db_utils.py`，实现通用装饰器 `async_db_retry`：
- **智能识别**: 仅捕获 `OperationalError` 中包含 "locked", "busy", "io error" 的异常进行重试。
- **混合策略**: 采用 **指数退避 (Exponential Backoff)** 结合 **随机抖动 (Jitter)**，避免重试时的惊群效应。
- **双层兼容**: 提供了 `retry_on_db_lock` 别名，确保与现有代码仓库的兼容。

### 2.3 仓库层加固
在以下核心仓库的写入路径应用了重试保护：
- **TaskRepository**: `push`, `complete`, `fail`, `reschedule`
- **StatsRepository**: `flush_logs`, `increment_stats`, `increment_rule_stats`
- **DedupRepository**: `add_or_update`, `batch_add`, `save_config`

## 3. 验证结果
- **语法校验**: `py_compile` 通过，无语法错误。
- **单元测试**: `tests/unit/repositories/test_task_repo.py` 在内存数据库模式下运行正常，功能链路完整。
- **代码审计**: 确认 `DedupRepository` 中抑制重试的 `try-except` 已移除，转由装饰器统一管理。

## 4. 结论与后续
本次修复通过"配置延长等待"与"逻辑失败重试"的双重机制，显著提升了系统在压力下的数据库鲁棒性。

**建议关注**:
- 观察磁盘 IO 压力，若 IOWAIT 过高，可能需要考虑将 SQLite 迁移至 PostgreSQL。
- 监控 WAL 文件大小，确保 `/data/db` 目录磁盘空间充足。
