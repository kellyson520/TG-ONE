# API 性能优化与并发控制 (API Performance & Concurrency Optimization)

## 背景 (Context)
从 `app.log` 分析发现，系统在处理高并发消息或官方 API 调用时存在严重的延迟波动。`get_chat_statistics` 等核心 API 耗时经常达到 30s-93s，主要原因是并发请求未合并（惊群效应）以及部分阻塞调用（如 `get_entity`）缺少超时保护，且大量重复的缓存命中日志导致了噪音。

## 核心策略 (Strategy)
1. **Request Coalescing (单一飞翔)**: 确保同一资源的并发请求合并为一次 API 调用。
2. **Global Concurrency Guard (全局门禁)**: 使用信号量限制同时发往 Telegram 的请求数，防止频率限制。
3. **Hard Timeout (强制超时)**: 对所有官方 API 的实体获取增加硬超时（5s/8s）。
4. **Log Cleanliness (日志降噪)**: 将高频缓存日志级别降为 DEBUG。

## 待办清单 (Checklist)

### Phase 1: 基础设施增强 (Infrastructure)
- [x] 在 `core/cache/unified_cache.py` 中引入 `RequestLock` 异步锁字典。
- [x] 优化 `@cached` 装饰器，实现请求合并机制 (Coalescing)。
- [x] 将 `@cached` 的"成功命中心"日志级别改为 DEBUG。

### Phase 2: API 逻辑重构 (API Refactoring)
- [x] 在 `services/network/api_optimization.py` 的 `TelegramAPIOptimizer` 中添加全局 `asyncio.Semaphore(10)`。
- [x] 重构 `get_chat_statistics` 方法：
    - [x] 为 `client.get_entity` 增加 `asyncio.wait_for(..., timeout=5.0)` 包装。
    - [x] 确保在信号量上下文内执行具体的 API 请求。
- [x] 重构 `get_users_batch` 方法：
    - [x] 增加批处理阈值检查和超时保护。

### Phase 3: 验证与验收 (Verification)
- [x] **并发测试**: 模拟 20 个 goroutine 并发请求同一 `chat_id` 的统计信息，验证 API 实际只被调用 1 次。
- [x] **性能监控**: 编写单元测试验证并发逻辑。
- [x] **归档报告**: 编写 `report.md` 并更新 `process.md`。
