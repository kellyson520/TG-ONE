# 任务名称 (Task Name)
SQLite 数据库高频并发死锁源头重构 (DB Write Batching & Sharding)

## 背景 (Context)
在 `20260311_Memory_And_Locking_Fix` 中采用了防卫性的延迟退避策略，但为了配合高并发吞吐量的根本需求，必须打破 SQLite 物理层面的单写锁约束。基于 `spec.md` 中的设计，我们将实施 CQRS 原理下的批处理单态写入（Async Batch Writer）和跨库数据文件物理分离规划，彻底终结 `OperationalError: database is locked`。

## 待办清单 (Checklist)

### Phase 1: 异步批处理组件 (Core Sink Construction)
- [x] 构建通用的缓冲池基类 (`core/helpers/batch_sink.py` 或由 `core/database.py` 提供单例管理器)，实现内存队列积压。
- [x] 封装独立的心跳刷新协程，利用 `asyncio.sleep` 与容灾控制定时排水 `flush_all()` 到 `session.execute()`。
- [x] 实现生命周期勾兑，在 `Application.on_shutdown` 时截停心跳，确保进程退出前所有缓冲同步安全落库。

### Phase 2: 任务流转异步化改写 (TaskRepo Refactor)
- [x] 移除 `repositories/task_repo.py` 高频点 (`complete()`, `fail()`) 的直接数据库事务与状态 CAS 锁定。
- [x] 将高频数据投递到指定的 `TaskStatusSink.put(...)` 供批处理器后台批量运行 `update().where(id.in_())`。
