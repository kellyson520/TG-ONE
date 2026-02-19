# Worker 性能提升方案 (Worker Performance Boost Spec)

## 1. 核心目标 (Core Objectives)
- **提升吞吐量**: 减少 SQLite 锁竞争导致的获取延迟。
- **降低 CPU 占用**: 优化轮询逻辑，减少无意义的数据库查询和上下文切换。
- **优化内存足迹**: 及时回收资源，防止任务堆积导致的内存溢出。

## 2. 方案细节 (Proposed Solutions)

### 2.1 生产者-消费者架构 (Centralized Fetching)
- **现状**: 15-40 个 Worker 同时调用 `fetch_next`，在高负载下 SQLite 频繁报 `database is locked`。
- **改进**: 
  - 引入 `TaskDispatcher` 类，作为唯一的任务拉取者。
  - 使用 `asyncio.Queue` (带 backpressure) 存储拉取到的任务。
  - Worker 仅从本地队列消费，不再直接操作 DB 获取任务。
- **优势**: DB 压力降低至原来的 1/N，锁竞争几乎消失。

### 2.2 批量拉取与预处理 (Batch Processing)
- **改进**: `TaskDispatcher` 每次拉取 5-10 个任务（而非 1 个），并提前完成 `json.loads(task_data)` 的开销操作。
- **优势**: 降低 SQL 执行频率，加快 Worker 启动速度。

### 2.3 极致弹性调度 (Refined Scaling)
- **改进**: 
  - 扩容步长根据积压量级动态调整（1/2/3 步进）。
  - 引入 `IO Wait` 或 `Event Loop Delay` 监控作为资源守卫（而不只是 CPU）。
- **优势**: 防止由于 IO 阻塞导致 CPU 虽低但系统响应慢的假象。

### 2.4 内存自动释放 (Auto-GC Logic)
- **改进**: 
  - 在 Worker 完成大任务或空闲 60s 后触发 `gc.collect(1)`。
  - 监控 `psutil` 的内存增长率，当斜率过高时触发全量回收。

### 2.5 SQLite 深度优化
- **改进**: 
  - 强制开启 `journal_mode=WAL`。
  - 设置 `synchronous=NORMAL`。
  - 配置 `mmap_size=256MB` 以提高读取效率。

## 3. 架构影响 (Architecture Impact)
- `WorkerService` 将作为协调者管理 `Dispatcher` 和 `WorkerPool`。
- `TaskRepository` 保持原样，但 `fetch_next` 的 `limit` 参数将被更有意义地使用。
