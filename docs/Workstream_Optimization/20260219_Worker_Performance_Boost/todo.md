# Worker 性能提升待办清单 (Worker Performance Boost Todo)

## Phase 0: 配置预设 (Config & Pre-flight)
- [x] 在 `.env.example` 和 `Settings` 中新增 `TASK_DISPATCHER_BATCH_SIZE` 等参数。
- [x] 新增内存熔断与延迟预警阈值。
- [ ] 确保核心日志级别已降级，防止日志本身产生高 IO。

## Phase 1: 架构重构 (Architecture)
- [x] **[已确认]** 并发上限维持在 **20**，启用 Dispatcher 缓解锁竞争。
- [x] 实现 `TaskDispatcher` 类 (`services/task_dispatcher.py`)，支持批量拉取与预解析。
- [x] 改造 `WorkerService`：接入 `asyncio.Queue` 与 Dispatcher 生命周期。
- [x] 优化 `TaskRepository`：验证批量拉取兼容性。

## Phase 2: 内存管理与响应监控 (Memory & Monitoring)
- [x] 修改 `core/helpers/sqlite_config.py`: 调优 `mmap_size` 与 `cache_size` 至适配 1G RAM 水平。
- [x] 实现 **"Loop Lag"** 监控协程并集成到 WorkerService。
- [x] 完善 **"内存熔断"** 逻辑，增加分级 GC 回收。

## Phase 3: 韧性与正确性 (Resilience & Correctness)
- [ ] 优化 Dispatcher 的 **惊群效应 (Thundering Herd)** 预防：
    - [x] 在退避方案中加入了指数增长与随机权重 (Jitter)。
- [ ] 媒体组聚合验证：
    - [x] 已实现 Dispatcher 侧的 `grouped_id` 集合分发，确保媒体组批量入队。
- [ ] **完善单例连接池共享**：
    - [ ] 在 `TaskDispatcher` 或 `Worker` 初始化阶段增加对源/目标 Chat 的实体预热 (`get_entity`)，减少 Telethon 内部的 `Entity Cache Miss`。
    - [ ] 确保 `RuleRepository` 的 TTL 缓存与 `Worker` 间的规则对象复用，减少内存波动。

## Phase 4: 统计与可观测性 (Observability)
- [x] 在 `get_system_status` 中整合了 Worker 性能统计信息。
- [x] 实现了 Dispatcher 吞吐量统计 (Tasks/Min)。
- [ ] **日志 I/O 降噪**：
    - [ ] 将 `WorkerService` 与 `TaskDispatcher` 中高频触发的 heartbeat 和 fetch 日志强制降级为 `DEBUG`。
    - [ ] 验证 `LOG_BUFFER_SIZE` 配置在 1G RAM 下的有效性，确保异步 Flush 避免磁盘 IO Wait。
- [ ] 监控 Swap 使用率变化，若 si/so 非零则在日志中警告。

## Phase 5: 验证 (Verification)
- [ ] 压力测试：向队列塞入 1000 个任务，观察 memory 波动曲线（重点关注 RSS 是否稳定在 600MB 以下）。
- [ ] 稳定性测试：运行 24 小时，检查是否由于长时间运行导致 RSS 缓慢溢出。
- [ ] 对比测试：验证 `database is locked` 错误频率相比旧版是否降低 90% 以上。
