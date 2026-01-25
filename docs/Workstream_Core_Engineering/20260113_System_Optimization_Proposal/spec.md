# 全链路系统优化建议书 (System Optimization Proposal)

> **目标**: 实现“高效、低占用、快速、稳定”的系统运行状态。
> **范围**: 覆盖基础设施、架构设计、数据库、业务逻辑及前端交互的全链路优化。

## 1. 基础设施层 (Infrastructure) - *基石*

这一层决定了系统的下限，目标是**极致的资源利用率**。

### 1.1 容器化优化 (Docker)
*   ✅ **Base Image**: 坚持使用 `python:3.11-alpine`，体积最小（~50MB），攻击面最小。
*   ✅ **Memory Allocator**: 强制使用 `jemalloc` (`LD_PRELOAD`)。
    *   *原理*: Python 默认的 malloc 在频繁分配小对象时容易产生碎片。Jemalloc 能有效控制碎片率。
*   **Container Limits**: 在 `docker-compose.yml` 中显式限制资源，防止 OOM 导致宿主机崩溃。
    ```yaml
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          memory: 128M
    ```

### 1.2 网络优化
*   **Keep-Alive**: 确保所有 HTTP/RPC 连接（Bot Client, Web Server）启用 TCP Keep-Alive，避免频繁握手。
*   **DNS Caching**: 容器内部启用 nscd 或在代码层面缓存 DNS 解析结果。

---

## 2. 核心架构层 (Core Architecture) - *引擎*

这一层提升系统的吞吐量，目标是**消除阻塞与冗余**。

### 2.1 高性能运行时
*   **uvloop**: 替换默认的 `asyncio` 事件循环。
    *   *收益*: HTTP 处理速度提升 2-4 倍，接近 Go 的性能。
    *   *实施*: `pip install uvloop` -> `import uvloop; uvloop.install()`
*   **orjson**: 替换标准 `json` 库。
    *   *收益*: 序列化速度提升 10-20 倍，内存占用更低。

### 2.2 内存模型优化
*   **Class Slots**: 对高频对象（如 `MessageContext`, `LogEvent`）使用 `__slots__`。
    *   *原理*: 禁用 `__dict__`，每个实例节省约 50% 内存，且属性访问速度更快。
*   **Object Pooling**: 对于极高频创建的对象（如 HTTP Request/Response 对象），复用对象池（如有必要，但在 Python 中通常 Slots 收益性价比最高）。

### 2.3 异步与并发
*   **非阻塞 I/O**: 严禁在 `async def` 中调用同步阻塞代码（如 `time.sleep`, `requests.get`, 普通文件读写）。
    *   *替代*: 使用 `aiohttp`, `aiofiles`, `asyncio.sleep`。
*   **结构化并发**: 使用 `asyncio.TaskGroup` (Python 3.11+) 管理并发任务，确保异常被正确捕获，任务被正确取消。

---

## 3. 数据库与持久化 (Persistence) - *瓶颈*

I/O 通常是性能瓶颈，目标是**读写分离与IO最小化**。

### 3.1 SQLite 深度调优 (针对单机高并发)
*   **WAL Mode**: `PRAGMA journal_mode = WAL;`
    *   *收益*: 读写不互斥，大幅提升并发吞吐量。
*   **Synchronous**: `PRAGMA synchronous = NORMAL;`
    *   *收益*: 在保证基本安全的前提下，大幅减少磁盘 fsync 次数。
*   **Mmap**: `PRAGMA mmap_size = 30000000000;`
    *   *收益*: 利用操作系统文件缓存，读取速度接近内存。

### 3.2 数据冷热分离
*   **定期归档**: 每天将超过 7 天的日志/历史记录导出为 `Parquet` 或 `CSV.gz` 并从 SQLite 删除。
    *   *Parquet*: 列式存储，压缩率极高，分析查询极快（比 JSON/CSV 快几十倍）。
*   **索引精简**: 定期检查 `sqlite_stat1`，删除不再使用的索引，减少写入开销。

### 3.3 连接池管理
*   **SQLAlchemy QueuePool**: 显式配置连接池。
    *   `pool_size=20`, `max_overflow=10`
    *   避免每次请求新建连接的开销。

---

## 4. 业务逻辑层 (Business Logic) - *大脑*

这一层决定处理效率，目标是**精准与批处理**。

### 4.1 智能去重 (Deduplication)
*   **Bloom Filter (布隆过滤器)**: 在查询数据库前，先查内存中的 Bloom Filter。
    *   *收益*: 99% 的“未重复”判断由于无需查库，仅仅是内存位运算，耗时从 ms 级降至 ns 级。
*   **LRU Cache**: 缓存最近 N 条处理过的 Message ID。

### 4.2 批处理 (Batching)
*   **批量日志写入**: 不要每条日志都写库。使用 `BatchQueue`，积攒 50 条或每隔 1s 批量插入一次。
    *   *收益*: 数据库事务开销降低 50 倍。
*   **批量转发 (可选)**: 如果业务允许，可合并多条消息转发（Telegram API 限制较多，需谨慎）。

### 4.3 正则优化
*   **Pre-compile**: 所有正则规则在启动时通过 `re.compile` 预编译。
*   **Re2**: 考虑使用 Google 的 `re2` 库（Python wrapper `google-re2`），防止正则回溯攻击，且速度更稳定。

---

## 5. 稳定性与全链路保障 (Stability) - *护盾*

这一层保障系统长期运行，目标是**自愈与防崩**。

### 5.1 熔断机制 (Circuit Breaker)
*   当目标 API (Telegram) 连续报错 N 次，暂停转发 M 秒。防止无意义的重试耗尽资源或触发封号。

### 5.2 优雅停机 (Graceful Shutdown)
*   捕获 `SIGTERM`。
*   停止接收新消息 -> 等待待处理任务队列清空 -> 关闭数据库连接 -> 退出。
*   确保数据零丢失。

### 5.3 监控与追踪 (Observability)
*   **Trace ID**: 全链路日志追踪（已实施）。
*   **Metrics**: 暴露 `/metrics` 接口（Prometheus 格式），监控：
    *   内存占用
    *   CPU 使用率
    *   队列堆积长度 (关键拥塞指标)
    *   API 响应时间

---

## 6. 前端体验 (Web UI) - *门面*

*   **SPA 优化**: 路由懒加载 (Lazy Loading)，首屏只加载 Dashboard。
*   **WebSocket**: 使用 WebSocket 推送日志和状态，代替 `setInterval` 轮询，减少服务器 HTTP 握手压力。
*   **静态资源缓存**: 配置 Nginx/FastAPI 对 CSS/JS/Images 设置长期 Cache-Control。

---

## 7. 实施优先级建议

| 优先级 | 动作 | 复杂度 | 收益 |
| :--- | :--- | :--- | :--- |
| **P0** (立即可做) | 启用 `uvloop` & `orjson` | 低 | 高 (CPU/Latency) |
| **P0** (立即可做) | SQLite WAL & Synchronous 配置 | 低 | 极高 (DB Concurrency) |
| **P0** (立即可做) | Data Class 添加 `__slots__` | 中 | 中 (Memory) |
| **P1** (短期规划) | 批量日志写入 (Batch Insert) | 中 | 高 (Disk I/O) |
| **P1** (短期规划) | 路由懒加载 & WebSocket改造 | 中 | 高 (User Exp) |
| **P2** (长期规划) | 布隆过滤器去重 | 高 | 高 (在大数据量下) |
| **P2** (长期规划) | 数据归档系统 (Parquet) | 高 | 高 (Long-term Stability) |
