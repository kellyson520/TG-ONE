# 归档管理器数据库锁死修复 (Archive Manager DB Locked Fix)

## 背景 (Context)
归档周期(`run_archiving_cycle`)执行时，在查询旧数据总量(`count_stmt`)处遭遇 `sqlite3.OperationalError: database is locked`。原因在于全局的 `BEGIN IMMEDIATE` 会为所有隐式事务分配写锁（或排他性操作），在高并发写入（如 hotword_service 刷写）场景下导致获取锁超时。

## 待办清单 (Checklist)

### Phase 1: 代码修复
- [x] 调整 `archive_manager.py` 中的 `OperationalError` 和 `asyncio` 导入位置至函数顶部
- [x] 为 `count_stmt` 执行增加重试逻辑，解决 `database is locked` 导致的周期异常
- [x] 验证现有 Fetching / Deleting 逻辑的重试是否在异常发生时能正常工作

### Phase 2: 验证与归档
- [x] 检查代码是否有语法错误和循环导入
- [x] 生成 `report.md`
- [x] 更新全局 `process.md`
