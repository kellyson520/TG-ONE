
# 数据库自动修复机制 (Cloud VPS Fix)

针对在云端 Linux VPS 环境下可能出现的 `sqlite3.OperationalError: disk I/O error` 问题，已实施以下自动修复机制：

1.  **启动时自动检测与清理** (`core/bootstrap.py`):
    *   在系统启动时，自动检查 `task_queue` 表中已完成或失败的任务数量。
    *   如果积压超过 **10,000** 条，将自动执行紧急清理 (`DELETE`)，防止数据库膨胀导致的 I/O 错误。
    *   清理后自动执行 `ANALYZE` 更新统计信息，确保查询优化器正常工作。

2.  **定期维护任务** (`core/db_factory.py`):
    *   在原有的日志清理任务 (`async_cleanup_old_logs`) 中，追加了对 `task_queue` 表的维护逻辑。
    *   定期删除过期的 `completed`/`failed` 任务，保持数据库轻量化。

3.  **建议配置**:
    *   在 Linux/VPS 环境下，建议检查 SQLite 版本。
    *   如果并发量极大，建议在 `.env` 中适当降低 `WORKER_MAX_CONCURRENCY` (例如设置为 10-20)，以减少 SQLite 文件锁定冲突。

此方案无需手动操作数据库，部署代码并重启服务即可自动触发修复。
