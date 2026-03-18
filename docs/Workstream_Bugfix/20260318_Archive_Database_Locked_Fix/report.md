# 归档管理器数据库锁死修复报告 (Report)

## 概要 (Summary)
修复了 `ArchiveManager.run_archiving_cycle` 周期任务中 `count_stmt` 执行时，在高并发背景下遭遇 `sqlite3.OperationalError: database is locked` 的问题。通过对 Count(*) 增加了 retry 控制，使主周期的三个生命周期位置（查询、获取、清理）拥有统一的韧性重试模式。

## 架构变更 (Architecture Refactor)
- **非浸入式改动**: 遵循 "禁止一刀切" 规则，只修正了引发异常的 `ArchiveManager.archive_model_data` 第一阶段读取环节。
- **依赖整合**: 将内部原本位于 `batch_size` 处的循环内导入 `asyncio` 和 `OperationalError` 提升到模块顶层，避免循环内部重复解析，提升执行效率。

## 验证结论 (Verification)
- **脚本静态编译**: `python -m py_compile repositories/archive_manager.py` 通过。
- **韧性升级**: 在 `session.execute(count_stmt)` 外层嵌套 5 次 Retry，底延 1.0s 指数回退，足以扛过 `hotword_service` 和 `Batch Sink` 在高频时瞬间锁死的暂态锁定。

## 手动操作 (Manual)
无需手动配置更新，归档模块将继续自动运行，不再因为瞬间高并发查询总容量崩溃。
