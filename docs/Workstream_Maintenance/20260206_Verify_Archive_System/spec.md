# 归档系统技术规范 (Spec)

## 1. 核心变更
### 1.1 ArchiveManager 升级
- **动态阈值**: 自动关联 `settings.HOT_DAYS_LOG`, `settings.HOT_DAYS_SIGN`, `settings.HOT_DAYS_STATS`。
- **Bloom 同步**: 在归档 `MediaSignature` 时，自动将其 `signature` 和 `content_hash` 同步到 Bloom 索引，确保冷数据依然可通过 Bloom 快速判定。
- **分批删除**: 归档成功后，分批从原库删除数据，避免长事务锁表。

### 1.2 归档任务简化
- `db_archive_job.py` 不再实现具体的归档 SQL 逻辑，而是作为 `ArchiveManager` 的调度外壳。
- 统一使用 `async_db_session`，保证异步环境下的上下文安全。

## 2. 测试与验证规范
- **全链路测试**: 通过 `scripts/test_archive_flow.py` 模拟数据生产 -> 归档 -> 跨库查询。
- **环境整洁**: 任何初始化测试（如 `archive_init.py`）生成的测试文件（123.bf, 999999.bf）必须在验证后立即删除。

## 3. 运维指标
- 统计归档耗时与成功记录数，上报至 Prometheus 监控项 `ARCHIVE_RUN_SECONDS` 和 `ARCHIVE_RUN_TOTAL`。
