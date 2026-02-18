# 修复 SQLite 数据库锁定错误 (修复任务队列更新失败)

## 背景 (Context)
在消息转发过程中，`task_repo.py` 执行任务状态更新（如标记为失败）时频繁出现 `(sqlite3.OperationalError) database is locked`。
这导致部分任务状态无法正确更新，且可能引发重试风暴。

## 策略 (Strategy)
1. **连接优化**: 确保 SQLite 开启 WAL 模式，并增加 `connect_args={"timeout": 30}`。
2. **重试机制**: 在核心 Repository 操作中引入异步重试机制 (`tenacity`)。
3. **事务优化**: 简化 `task_repo.py` 中的 SQL 操作，确保事务尽可能短。

## 待办清单 (Checklist)

### Phase 1: 诊断与分析
- [x] 检查 `task_repo.py` 中的关键写入路径 (`fail`, `complete`, `push`)
- [x] 分析 `.log` 文件中的死锁堆栈 (确认是 `task_queue` 更新锁)
- [x] 评估现有 `busy_timeout` (当前 5s -> 建议 30s)

### Phase 2: 实施优化
- [x] 创建 `core/helpers/db_utils.py` 包含异步重试装饰器 `async_db_retry`
- [x] 修改 `core/database.py` 的 `PRAGMA` 配置 (WAL 模式, busy_timeout=30s)
- [x] 修改 `core/db_factory.py` 同步 PRAGMA 标准
- [x] 在 `TaskRepository` 各个写入方法中应用重试机制
- [x] (可选) 在 `StatsRepository` 和 `DedupRepository` 中同步重试机制

### Phase 3: 验证与验收
- [x] 静态代码检查 (py_compile)
- [x] 运行基础单元测试 (`test_task_repo.py`)
- [x] 验证兼容性别名 `retry_on_db_lock`

### Phase 4: 报告与归档
- [x] 生成 `report.md`
- [x] 更新 `docs/process.md` 状态
