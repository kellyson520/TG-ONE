# VPS 高负载 (300%) 修复 (VPS High Load Fix)

## 背景 (Context)
用户反馈在 VPS 上运行时 CPU 负载达到 300%。
初步分析原因为：
1. `WorkerService` 在积压严重时过度扩容（最高 40 并发）。
2. SQLite 数据库在高并发写操作下性能下降并可能导致重试频率过高。
3. 日志记录过于频繁，增加了系统负担。
4. 资源监控逻辑在 async 环境下可能不准确。

## 待办清单 (Checklist)

### Phase 1: 监控与诊断 (Diagnostic)
- [x] 分析日志以确认高负载期间的系统行为。
- [x] 优化 `WorkerService` 中的资源监控逻辑，确保负载评估准确。
- [x] 实现更详细的指标收集（CPU/内存占用的细分）。

### Phase 2: 并发控制优化 (Concurrency Control)
- [x] 调整 `WorkerService` 扩容算法，增加扩容间隔和降低步长。
- [x] 降低默认 `WORKER_MAX_CONCURRENCY` 从 40 降至平衡值（目前设为 15）。
- [x] 优化 `fetch_next` 逻辑，减少数据库竞争（已确认逻辑健壮性，主要靠并发控制）。
- [x] 优化 SQLite 连接池设置，针对单文件数据库降低并发限制。

### Phase 3: 系统负载保护 (Resource Protection)
- [x] 强化 `Resource Guard`，当 CPU 持续高位时主动缩减 Worker。
- [x] 优化日志缓冲区，减少 IO 占用（降级 API 日志至 WARNING）。
- [x] 识别并优化高 CPU 消耗的子功能（优化了 API 处理中的日志与 yield 逻辑）。

### Phase 4: 验证与验收 (Verification)
- [ ] 在高负载模拟环境下测试。
- [ ] 验证 CPU 占用率是否下降且吞吐量保持稳定。

Implementation Plan, Task List and Thought in Chinese
