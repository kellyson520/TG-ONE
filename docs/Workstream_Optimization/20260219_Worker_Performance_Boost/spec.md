# Worker 性能提升方案 (Low-Resource VPS Optimized)

## 1. 核心目标 (Core Objectives)
- **极简内存占用**: 针对 **1GB RAM** 环境，通过 `mmap` 控制和主动 GC 规避 Swap 换入。
- **高能效比**: 借鉴 **Nginx** 的事件驱动思想，将 20 并发 Worker 的上下文切换开销通过 `Dispatcher` 降至最低。
- **高可靠性**: 借鉴 **Celery/SQS** 的租约机制 (Visibility Timeout)，确保任务在崩溃后能自动赎回。

## 2. 方案细节 (Proposed Solutions)

### 2.1 生产者-消费者架构 (Inspired by Celery & Go Channels)
- **Dispatcher (Producer)**: 
    - **Prefetch 机制**: 不再单个拉取，而是根据 Worker 繁忙程度批量拉取 (一次 10-20 条)。
    - **Backpressure (背压)**: 当 `asyncio.Queue` 满载时，Dispatcher 进入阻塞等待，防止内存中积压过多待处理对象。
- **Worker (Consumer)**: 保持 **20** 并发，但职责简化为纯粹的消息处理，不再触碰 DB 轮询逻辑。

### 2.2 响应式负载守卫 (Inspired by Nginx & Node.js)
- **Loop Lag 监控**: 
    - 采用 "心跳延迟测定法"。若事件循环处理一轮 `sleep(0)` 的时间超过 200ms，自动触发 Dispatcher 休眠。
    - **意义**: 在 2 CPU 环境下，这是防止系统进入 "雪崩效应" 的最前哨指标。

### 2.3 SQLite 内核级调优 (Inspired by SQLite Performance Best Practices)
- **写入串行化**: 维持 `BEGIN IMMEDIATE` 模式。
- **内存映射控制**: 鉴于 1G RAM 限制，将 `mmap_size` 固定在 **64MB**。这借鉴了数据库引擎在内存受限环境下的 "指针映射" 策略，减少 Read 系统调用。
- **WAL 检查点优化**: 在任务高峰期后自动触发 `PRAGMA wal_checkpoint(PASSIVE)`，控制 `.db-wal` 文件体积。

### 2.4 任务租约与幂等保护 (Inspired by Amazon SQS)
- **Lease-based Lock**: 任务锁定后拥有 15 分钟 "可见性超时"。
- **Dispatcher 自动续约**: 对于执行特别耗时的任务（如大视频下载），由 Worker 向 Dispatcher 发送信号延长租约，防止任务被重复分配。

## 3. 架构影响 (Architecture Impact)
- **解耦**: 数据库连接池将由 `Dispatcher` 和 `Worker` 共同持有共享，但 SQL 执行频率下降 60% 以上。
- **资源隔离**: 确保 GC 回收和任务解析处于不同的 CPU Tick 中（通过 `yield`）。

## 4. 质量矩阵 (Quality Matrix)
- [ ] RSS 内存曲线呈 "锯齿状" 平稳运行，不出现单调递增。
- [ ] SQLite `SQLITE_BUSY` 报错率从当前水平下降 90%。
- [ ] 24 小时运行无 OOM 风险。
