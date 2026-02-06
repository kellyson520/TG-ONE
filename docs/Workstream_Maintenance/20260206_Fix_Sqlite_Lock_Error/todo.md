# 修复 SQLite 数据库锁定错误 (Fix SQLite Database Locked Error)

## 背景 (Context)
归档任务 `scheduler.db_archive_job` 在执行 `ChatStatistics` 和 `RuleStatistics` 归档后的删除操作时，频繁遭遇 `(sqlite3.OperationalError) database is locked` 错误。这通常是由于并发写入竞争或事务持有时间过长导致的。

## 待办清单 (Checklist)

### Phase 1: 诊断与分析
- [ ] 检查 `ArchiveManager` 中的删除逻辑，评估 batch size 对锁的影响
- [ ] 检查是否存在未关闭的只读事务阻塞了写入
- [ ] 验证 WAL 模式设置是否在所有连接中生效

### Phase 2: 核心修复
- [ ] 在 `ArchiveManager` 的删除操作中增加指数回退重试机制
- [ ] 优化删除逻辑，减小单次事务中的删除量（减小 batch size 或增加 yield）
- [ ] 确保 `archive_once` 不会在同一个 loop 中重复启动多个 task (修复 `scheduler/db_archive_job.py` 中的重复定义)

### Phase 3: 验证与监控
- [ ] 手动触发强制归档流程，验证锁错误是否消除
- [ ] 运行集成测试 `tests/integration/test_archive_flow.py`
- [ ] 检查日志输出，确保重试机制生效且任务最终成功

### Phase 4: 闭环
- [ ] 生成报告 `report.md`
- [ ] 更新 `docs/process.md`
