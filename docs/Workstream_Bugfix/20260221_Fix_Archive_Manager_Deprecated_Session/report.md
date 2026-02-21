# Fix Archive Manager Deprecated Session Report

## Summary
修复了 `ArchiveManager` 在执行归档任务时因使用已废弃的同步 `db_session` 而导致的 `NotImplementedError`。将默认的 `session_factory` 统一为 `async_db_session`。

## Changes
### repositories/archive_manager.py
- 将 `get_archive_manager` 函数中的默认 `session_factory` 从 `db_session` 更改为 `async_db_session`。
- 引入了延迟导入以避免循环依赖。

## Verification
### Tests
- 创建了测试脚本 `tests/verify_archive_session_fix.py`。
- 验证了 `get_archive_manager()` 返回的实例能够成功通过其 `session_factory` 开启异步数据库会话并执行查询。
- 测试结果：
  ```
  Session factory is: <function async_db_session at ...>
  Successfully opened async session.
  Query result: 1
  ```

## Manual
无特殊操作，系统背景归档任务或通过 Web Admin 触发的归档任务现在应能正常运行。
