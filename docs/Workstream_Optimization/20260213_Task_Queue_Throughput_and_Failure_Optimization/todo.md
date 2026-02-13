# 任务队列吞吐量优化与失败治理 (Task Queue Throughput & Failure Optimization)

## 背景 (Context)
当前任务队列积压严重（约 8.8 万条 Pending），但系统活跃处理能力极低（始终保持在 2 个 Running Workers），且近期失败率接近 50%（全量为 "Source message not found"）。
这表明：
1. `WorkerService` 的动态伸缩机制失效。
2. 任务积压过久导致大量过时消息被清理，形成大量无效处理负载。
3. 系统吞吐量不足以应对当前的转发压力。

## 策略 (Strategy)
1. **诊断并修复动态伸缩**: 检查 `WorkerService` 为何不根据积压量扩容到 `MAX_CONCURRENCY`。
2. **失败治理 (Dead Letter Handling)**: 针对 "Source message not found" 进行快速失败处理，避免无效轮询，并清理极旧的无效任务。
3. **并发调优**: 优化信号量控制逻辑，在安全范围内提升单机并发上限。
4. **性能验证**: 观察处理速度是否提升，失败率是否下降。

## 待办清单 (Checklist)

### Phase 1: 现状诊断与伸缩修复
- [ ] **扩容状态审计**:
    - [ ] 编写脚本检查 `WorkerService` 内存中 `self.workers` 的实际长度。
    - [ ] 打印 `_monitor_scaling` 循环的日志，检查是否在中途由于数据库连接超时而抛出异常。
- [ ] **性能基准测试**:
    - [ ] 测试 `task_repo.get_queue_status()` 在 8.8w 行数据下的响应时间。
    - [ ] 测试 `task_repo.fetch_next()` 的 SQL 执行计划，确认是否命中索引。
- [ ] **逻辑修复**:
    - [ ] 在 `worker_service.py` 中增加对监控协程的异常捕获与自动重启。
    - [ ] 调整 `target_count` 的计算逻辑，改为更激进的扩容系数，并强制在积压 > 1000 时保持 `MAX_CONCURRENCY`。
- [ ] **手动干预**: 尝试通过日志确认是否需要重启进程以强制重置 Worker 状态。

### Phase 2: 失败负载抑制 (治理 "SourceNotFound")
- [ ] **数据清洗**:
    - [ ] 执行 SQL 统计 `Source message not found` 的任务时间分布。
    - [ ] **[MANDATORY]** 执行批量标记：将超过 48 小时的所有 `pending` 同步任务标记为 `failed` (Expired)，立即减少 8w 的待处理量。
- [ ] **代码加固**:
    - [ ] 修改 `WorkerService._process_task_safely`，在捕获到消息不存在时，不再进入 `_retry_group` 或 `reschedule` 逻辑，直接 `complete` 或标记为 `permanent_fail`。
    - [ ] 优化 `get_messages_queued` 的缓存逻辑，防止对同一个不存在的消息反复发起 API 请求。
- [ ] **积压隔离**: 实现“新旧分离”，优先处理 `created_at` 在 15 分钟内的任务，将旧任务放入背景慢速队列。

### Phase 3: 并发与吞吐优化
- [ ] **DB 索引优化**: 
    - [ ] 执行 `CREATE INDEX IF NOT EXISTS idx_task_queue_fetch ON task_queue (status, scheduled_at, priority, created_at);`
- [ ] **批量 Fetch 增强**:
    - [ ] 修改 `fetch_next` 的 `limit(1)` 为动态 `limit(batch_size)`，允许一个事务锁定多个任务。
- [ ] **流量窗口调优**: 
    - [ ] 将 `FORWARD_MAX_CONCURRENCY_GLOBAL` 从 3 调整为 5-8，观察 Telegram 是否报错。
    - [ ] 减小 Worker 的休眠步进 (`sleep_increment`)，使其在有任务时更快速响应。

### Phase 4: 结果验证
- [ ] 实时监控 `running` 值的变化趋势。
- [ ] 统计 10 分钟内的 `completed` 增速与 `failed` 增速。
- [ ] 生成处理效能报告。
