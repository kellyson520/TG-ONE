# 数据库并发写锁彻底解决技术方案 (CQRS & Batching Specs)

## 1. 背景问题描述 (Context & Problem Statement)

在之前 `20260311_Memory_And_Locking_Fix` 的重构中，我们采用了 `Jitter Exponential Backoff` 作为**防守型**策略，短暂地避开了报错毛刺并且缓解了死锁压力。

但是，`TG ONE` 系统的重度并发业务场景下（如 Worker 每毫秒高频率完成或失败多条记录任务），依赖了具有“文件级全局单写锁”物理限制的 **SQLite** 关系型数据库。由于多进程/协程同时拉起写事务的请求极其密集：
- 写操作争夺全局唯一通道时产生了高延迟。
- 并发请求数 > SQLite 退避最大时间范围时，依然无法阻止等待队列饱和乃至 `OperationalError: database is locked`。
- 退避和自适应休眠是以牺牲系统有效吞吐量（TPS）为代价换取的表面太平。

## 2. 方案目标 (Objectives)

从**源头架构级**彻底化解并分离这道锁冲突问题。
以“空间换时间”的缓存和聚合策略，变无序并行操作为单线程串行批处理，释放 SQLite 的极大性能：

*   **100% 消除重度任务场景下的 SQLite 多并发死锁报错** (`database is locked`) 及其退避带来的逻辑等待时间。
*   将单条记录的数次写事务消耗，合并压缩为单个大事务的多行执行（100 -> 1 次 fsync 系统调用），预期核心表写性能飙升。
*   符合 **TLM 规范架构**，不侵入现有数据表模型和使用方逻辑（保持上层调用 API `async_db_retry` 及原本 `await repo.complete(task_id)` 在语义设计上的兼容性）。

## 3. 架构设计 (Architecture Design: CQRS & Single-Writer Sink)

核心理念是融合 **批处理 Sink + 单消费者（Single Writer)**。

### 3.1 引入 `AsyncBatchWriter`
*   定位: `core.database` 下或 `services` 的核心组件。
*   职责:
    *   在内存中建立一个安全的 `asyncio.Queue` 充当消息总线 (Message Bus)。
    *   启动唯一的守护循环 (Daemon Coroutine)。负责以固定的心跳间隙 (例如 `150ms`) 或积压达到一定阈值 (例如 `2000` 条) 时，将队列中的数据流出，一次事务性封装执行 `executemany`。

### 3.2 服务调用方的适配改造 (Repository 层注入)
如 `repositories/task_repo.py` 及未来所有的日志表（`audit_logs`、`system_logs`、`forward_records` 等）。
*   原本 `complete()`：直接执行 `update(TaskQueue).where(...)` -> `commit()`。
*   改造后：直接将更新参数 `{'task_id': 100, 'status': 'completed'}` 组合为命令字典，立即放入全局的 `task_status_sink.put(...)`，协程即刻 `return` 结束，不发生任何锁阻塞操作。

### 3.3 数据库级别分离 (Database Vertical Sharding)[已废弃]
鉴于 `TG ONE` 严格的 KISS (简洁至上) 原则与 SQLite 物理外键关联（例如 `RuleLog` 等强关联）现状，跨文件分离的实施成本远高于收益。**物理分离方案已被管理层否决**。我们完全依赖前两步“异步写汇聚”的架构降维即可抹平锁死问题，继续维持单体 `tg_one.db` 文件的极简便携性。

## 4. 实施阶段拆解 (Implementation Steps)

### Phase 1: 异步批处理 Sink 基建 (`AsyncBatchWriter` 实现)
1. 设计 `BaseBatchSink` 组件，具备启动事件循环的方法、超时汇聚和批量持久化的核心逻辑。
2. 配置参数化：`max_batch_size=500`, `flush_interval_ms=100`。
3. 提供基础异常保护与重入机制。如遇到批处理事务提交失败时，使用优雅的回退写模式或将死信数据转移。

### Phase 2: 热点资源改造 (TaskQueue & Records 改写)
1. 基于上述组件创建 `TaskStatusSink` 单例。
2. 重构 `repositories/task_repo.py` 中的 `complete()` 与 `fail()`：
    *   屏蔽直接 `UPDATE`。
    *   变更为构建 `payload` 塞入单例队列：`await TaskStatusSink.put({"id": task_id, "action": "complete"})`。
3. `TaskStatusSink` 消费者逻辑通过 `update().where(TaskQueue.id.in_(completed_ids))` 方式分状态一次性聚合更新。

### Phase 3: DB 表级别硬隔离 (废弃)
- `[Skip]` 基于 KISS 与 ROI 综合评估，彻底放弃破坏物理外键的方案，保留应用代码内的关联 Join 原生生态。

## 5. 挑战与回退策略 (Risks & Fallbacks)

*   **进程崩溃数据丢失**: 因为状态暂存于由于 Python 内存 `Queue`，若遇到机器硬重启或 `ps kill -9` 瞬间，这 100ms 窗口由于 `UPDATE` 或 `INSERT` 未持久化可能丢失。
*   **补偿机制**: 
    1.  依赖于 `TaskDispatcher` 原本的 `rescue_stuck_tasks` 补漏：即如果 `completed` 这种高频终态数据由于重启丢失，最终它一直处于 `running` 超时，调度器会再重新捞取执行（具备幂等性的状态可重放）。
    2.  `Application.on_shutdown()` 生命周期注册强制排水 (Drain All) 的 `flush_all()` 操作，保证优雅重启时业务安全落库。
