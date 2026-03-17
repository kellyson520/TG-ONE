# StatsRepo 高频写热点批处理化优化

## 背景 (Context)
VPS 监控显示内存长期 90%+，磁盘 IO 延迟峰值高达 **289,169ms（~4.8分钟）**，进程于 04:54 崩溃。
根因：`stats_repo.py` 中的 `increment_stats()` 与 `increment_rule_stats()` 每条消息直接触发 DB 写操作，无任何缓冲，导致 SQLite 写锁极度饱和。

## 核心策略 (Strategy)
**CQRS 内存累加器模式**：写路径改为纯内存 `+=` 累加，读路径不变。
`_cron_flush` 采用 **双触发 + AIMD 自适应调度**：大小触发（黄色水位 event）+ 时间触发（动态间隔 1s~30s），高峰自动提速、空闲自动降频。
`_log_buffer` 溢出防护升级为**三水位线 + 等级感知驱逐**（ERROR/CRITICAL 永不丢弃）。
同时修复 `BatchSink` 失败静默丢数据问题。

## 待办清单 (Checklist)

### Phase 1: `stats_repo.py` 核心改造
- [x] 新增 `_chat_stats_buffer: dict[tuple, dict]` 内存累加器字段
- [x] 新增 `_rule_stats_buffer: dict[tuple, dict]` 内存累加器字段
- [x] 新增 `_stats_lock = asyncio.Lock()` 保护 stats buffer
- [x] 新增 `_flush_event = asyncio.Event()` 用于大小触发唤醒
- [x] 新增 `_flush_scheduler = AIMDScheduler(min=1s, max=30s, incr=5, mult=0.5)` 自适应调度器
- [x] 重构 `increment_stats()`：改为纯内存 `+= 1`，不触发 DB
- [x] 重构 `increment_rule_stats()`：改为纯内存 `+= 1`，不触发 DB
- [x] 新增 `flush_stats()` 方法：将内存累加器批量 upsert 到 DB（一次事务）
- [x] 改造 `_cron_flush()`：`asyncio.wait_for(event, timeout=aimd_interval)` 双触发循环，执行后反馈 AIMD
- [x] 修改 `stop()` 在关闭时同时排水 `flush_stats()`

### Phase 2: OOM 防护 — 三水位线 + 等级感知驱逐
- [x] 定义三水位常量：`LOG_BUFFER_WARN=2000` / `LOG_BUFFER_EVICT=3500` / `LOG_BUFFER_HARD_CAP=5000`
- [x] 在 `log_action()` 中写入 `"level"` 字段（INFO/WARNING/ERROR），供驱逐算法分桶
- [x] 实现 `_evict_by_level(buffer, keep_ratio)` 辅助函数：ERROR/CRITICAL 全保留，按优先级从低到高驱逐
- [x] 在 `log_action()` 中加入三档水位检测逻辑：黄色→触发 flush，橙色→驱逐+flush，红色→强制驱逐
- [x] 在黄色/橙色水位时 `self._flush_event.set()` 立即唤醒 `_cron_flush`
- [x] 定义 Stats Buffer 常量：`STATS_BUFFER_WARN=5000` / `STATS_BUFFER_CAP=10000`
- [x] 在 `increment_stats/rule_stats` 中：黄色水位→异步 flush，红色水位→**同步 await flush**（stats 不允许丢弃）

### Phase 3: `batch_sink.py` 失败重入队列修复
- [x] 修改 `_process_batch()` 的 `except` 块：失败时带 retry_count 重新入队
- [x] 设置重试上限 `max_retry = 3`，超限才永久丢弃并打 WARNING

### Phase 4: SQLite WAL 模式开启
- [x] 定位 `core/db_init.py` 数据库初始化位置
- [x] 添加 `PRAGMA journal_mode=WAL`
- [x] 添加 `PRAGMA synchronous=NORMAL`
- [x] 添加 `PRAGMA cache_size=-64000`（64MB 页缓存）
- [x] 添加 `PRAGMA busy_timeout=10000`（10s 超时）

### Phase 5: 验证
- [ ] 运行 `tests/unit/repositories/test_stats_repo.py`（新增 / 已有）
- [ ] 确认 `increment_stats` 不再直接触发 DB session
- [ ] 确认 `flush_stats` 能正确 upsert 累加值
- [ ] 模拟高频写（> 2000 条/s）验证黄色水位触发紧急 flush 且 buffer 不越界
- [ ] 模拟 ERROR 日志混入高频写，验证驱逐后 ERROR 全部保留
- [ ] 验证 AIMD 行为：高压时 `current_interval` 趋向 1s，空闲时趋向 30s
- [ ] 在测试环境下模拟高频写，确认无锁报错与 OOM
