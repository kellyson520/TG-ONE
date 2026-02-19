# 任务: 修复 SQLite 数据库锁定错误 (深度治理)

## 背景 (Context)
虽然之前已经实施了 WAL 模式和重试机制，但系统在高负载下仍偶发 `database is locked` 错误。特别是在 `task_queue` 表的更新操作中。这可能与 SQLite 的锁升级机制（Shared -> Reserved -> Exclusive）在高并发下的竞争有关。

## 策略 (Strategy)
1. **强制原子化事务**: 在写入连接中使用 `BEGIN IMMEDIATE`，确保在事务开始时就获取写锁。
2. **连接池优化**: 针对写操作，由于 SQLite 本质上只允许一个写者，限制写连接池大小或确保写操作排队。
3. **增强重试监控**: 在 `async_db_retry` 中添加更多调试日志，记录故障时的堆栈和重试细节。
4. **一致性修复**: 统一 `core/database.py` 和 `core/db_factory.py` 中的 SQLite 配置。

## 待办清单 (Checklist)

### Phase 1: 诊断与准备
- [ ] 创建复现脚本（压测模拟并发写入）
- [ ] 审计所有数据库写入路径，确认是否都使用了重试装饰器

### Phase 2: 核心配置加固
- [ ] 在 `set_sqlite_pragma` 中添加 `BEGIN IMMEDIATE` 监听器
- [ ] 确保 `AsyncEngine` 正确监听 `sync_engine` 的连接事件
- [ ] 统一并优化 `busy_timeout` 和缓存大小

### Phase 3: 代码层优化
- [ ] 审计 `TaskRepository` 和 `StatsRepository` 的长事务
- [ ] 优化 `async_db_retry` 的日志输出，包含调用方法名

### Phase 4: 验证与报告
- [ ] 运行压测脚本验证修复效果
- [ ] 生成任务报告
