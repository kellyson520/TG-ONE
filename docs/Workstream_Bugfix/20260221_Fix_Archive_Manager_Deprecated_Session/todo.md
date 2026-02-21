# Fix Archive Manager Deprecated Session

## 背景 (Context)
在执行数据归档周期时，`ArchiveManager` 遇到了 `NotImplementedError: 同步 db_session 已废弃，请使用 async_db_session`。这是因为 `ArchiveManager` 默认使用了已经废弃的同步 `db_session` 工厂。

## 待办清单 (Checklist)

### Phase 1: 修复实现
- [x] 修改 `repositories/archive_manager.py`，将默认 `session_factory` 改为 `async_db_session` [P0]
- [x] 检查并确保 `ArchiveManager` 内部所有对 `self.session_factory()` 的调用都是异步上下文管理器 (已确认为 `async with`) [P1]

### Phase 2: 验证与测试
- [x] 运行相关集成测试或手动触发归档任务 [P0]
- [x] 检查日志输出，确认不再报 session 错误 [P1]
