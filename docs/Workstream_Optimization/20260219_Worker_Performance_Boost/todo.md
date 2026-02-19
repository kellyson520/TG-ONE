# Worker 性能提升待办清单 (Worker Performance Boost Todo)

## Phase 1: 架构重构 (Architecture)
- [ ] 实现 `TaskDispatcher` 类，封装中央拉取逻辑。
- [ ] 改造 `WorkerService` 以支持 `Dispatcher` -> `Queue` -> `Worker` 流程。
- [ ] 优化 `TaskRepository.fetch_next` 的批量处理效率。

## Phase 2: 性能调优 (Tuning)
- [ ] 优化 `WorkerService` 的资源守卫 (Resource Guard)，加入 Loop Lag 监测。
- [ ] 实现 Worker 层的轻量化 GC 触发逻辑。
- [ ] 在 `database.py` 中注入高性能 SQLite PRAGMA 设置。

## Phase 3: 监控与保护 (Monitoring)
- [ ] 增强日志系统，在积压时输出更有意义的吞吐量指标。
- [ ] 优化 `_adaptive_sleep` 的退避曲线。

## Phase 4: 验证 (Verification)
- [ ] 进行小规模压力测试（确保在 2GB 内存限制内）。
- [ ] 验证 `database is locked` 错误出现频率是否下降。
- [ ] 确认 CPU 平均负载下降 20% 以上。
