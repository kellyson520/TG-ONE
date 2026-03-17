# 技术方案：StatsRepo 写热点批处理化 (CQRS 内存累加器)

## 1. 背景与问题 (Context)

### 根因链
```
每条消息触发转发
  ↓
increment_stats()      → UPDATE/INSERT + commit (1x fsync)
increment_rule_stats() → UPDATE/INSERT + commit (1x fsync)
  ↓
高并发场景下 SQLite 写锁争用
  ↓
磁盘 IO 延迟堆积至 289,169ms
  ↓
进程 OOM / 锁超时崩溃（04:54）
```

### 额外问题
1. `_log_buffer` 无容量上限 → flush 失败时无限增长 → OOM
2. `TaskStatusSink._process_batch` 写失败直接丢弃 → 静默数据丢失

---

## 2. 架构设计 (Architecture)

### 2.1 改造前 vs 改造后

| | 改造前 | 改造后 |
|---|---|---|
| `increment_stats` | 每次直接 UPDATE + commit | 内存 `dict[key] += 1` |
| `increment_rule_stats` | 每次直接 UPDATE + commit | 内存 `dict[key] += 1` |
| DB 落库时机 | 每条消息（可达 1000+ 次/s） | **双触发**：大小阈值 OR 自适应时间窗口 |
| 写操作次数 | N 次（N=消息数） | 1 次（合并所有累加值） |
| flush 间隔 | 无（每次立即写） | **AIMD 自适应**：1s（高峰）~ 30s（空闲） |

### 2.4 自适应 Flush 调度策略（双触发 + AIMD）

> **核心思路**：flush 间隔不固定，根据实际写入压力动态伸缩。复用项目已有的 `AIMDScheduler`。

#### 触发条件（OR 关系，满足任一即 flush）

```
触发 1（大小触发）：stats buffer 中 key 数 > STATS_BUFFER_WARN(5000)
触发 2（时间触发）：距上次 flush 经过的时间 >= current_interval（AIMD 动态值）
```

#### AIMD 自适应规则

| 场景 | flush 后 buffer 积压情况 | AIMD 响应 | 下次间隔趋势 |
|---|---|---|---|
| 高峰期 | 有大量积压（> 100 keys） | **乘法缩短**（×0.5） | 快速收敛至 1s |
| 空闲期 | 几乎为空（< 10 keys） | **加法延长**（+5s） | 逐渐放宽至 30s |

```python
# _cron_flush() 的自适应版本
_flush_scheduler = AIMDScheduler(
    min_interval=1.0,   # 高峰最快每 1s flush 一次
    max_interval=30.0,  # 空闲最慢每 30s flush 一次
    increment=5.0,      # 空闲时每轮 +5s
    multiplier=0.5      # 高峰时每轮 ×0.5
)

async def _cron_flush(self):
    while not self._shutdown_event.is_set():
        interval = self._flush_scheduler.current_interval
        try:
            # 等待计时器超时，或被大小触发器提前唤醒
            await asyncio.wait_for(self._flush_event.wait(), timeout=interval)
            self._flush_event.clear()
        except asyncio.TimeoutError:
            pass  # 正常超时，执行定时 flush

        # 执行 flush，根据实际积压量反馈 AIMD
        keys_before = len(self._chat_stats_buffer) + len(self._rule_stats_buffer)
        await asyncio.gather(self.flush_logs(), self.flush_stats(), return_exceptions=True)

        # 积压越多 → 间隔越短；积压越少 → 间隔越长
        had_pressure = keys_before > 10
        self._flush_scheduler.update(found_new_content=had_pressure)


# 在 increment_stats / log_action 内，到达黄色水位时唤醒 flush
if size >= LOG_BUFFER_WARN or keys >= STATS_BUFFER_WARN:
    self._flush_event.set()  # 立即唤醒，不等计时器到期
```



### 2.2 数据结构设计

```python
# 内存累加器结构
_chat_stats_buffer: dict[tuple[int, str], dict[str, int]]
# key: (chat_id, date_str)  例: (123456, "2026-03-17")
# val: {"forward_count": 42, "saved_traffic_bytes": 10240}

_rule_stats_buffer: dict[tuple[int, str], dict[str, int]]
# key: (rule_id, date_str)  例: (7, "2026-03-17")
# val: {"success_count": 30, "error_count": 2, "filtered_count": 5, "total_triggered": 37}
```

### 2.3 `flush_stats()` 核心逻辑

```python
async def flush_stats(self):
    """
    原子性：先 snapshot + clear，再异步落库。
    失败时不丢失，下次 flush 再合并（数据在析出前已 clear）。
    注意：若 flush 失败，本次 snapshot 数据将丢失。
    可接受：统计数据非关键路径，允许小量丢失。
    """
    async with self._stats_lock:
        if not self._chat_stats_buffer and not self._rule_stats_buffer:
            return
        chat_snap = dict(self._chat_stats_buffer)
        rule_snap = dict(self._rule_stats_buffer)
        self._chat_stats_buffer.clear()
        self._rule_stats_buffer.clear()

    async with self.db.get_session() as session:
        # 批量处理 ChatStatistics
        for (chat_id, dt), vals in chat_snap.items():
            stmt = update(ChatStatistics).where(
                ChatStatistics.chat_id == chat_id,
                ChatStatistics.date == dt
            ).values(
                forward_count=ChatStatistics.forward_count + vals.get("forward_count", 0),
                saved_traffic_bytes=ChatStatistics.saved_traffic_bytes + vals.get("saved_traffic_bytes", 0)
            )
            result = await session.execute(stmt)
            if result.rowcount == 0:
                await session.execute(insert(ChatStatistics).values(
                    chat_id=chat_id, date=dt, **vals
                ))

        # 批量处理 RuleStatistics
        for (rule_id, dt), vals in rule_snap.items():
            stmt = update(RuleStatistics).where(
                RuleStatistics.rule_id == rule_id,
                RuleStatistics.date == dt
            ).values(
                total_triggered=RuleStatistics.total_triggered + vals.get("total_triggered", 0),
                success_count=RuleStatistics.success_count + vals.get("success_count", 0),
                error_count=RuleStatistics.error_count + vals.get("error_count", 0),
                filtered_count=RuleStatistics.filtered_count + vals.get("filtered_count", 0),
            )
            result = await session.execute(stmt)
            if result.rowcount == 0:
                await session.execute(insert(RuleStatistics).values(
                    rule_id=rule_id, date=dt, **vals
                ))

        await session.commit()
```

---

## 3. 容量上限防护设计（三水位线自适应策略）

> **设计原则**：不允许一刀切。根据 buffer 当前水位动态调整行为，以日志等级为权重进行智能驱逐。

### 3.1 三水位线定义

```python
LOG_BUFFER_WARN     = 2000   # 黄色水位（40%）：触发紧急 flush，不丢弃
LOG_BUFFER_EVICT    = 3500   # 橙色水位（70%）：按等级驱逐低优日志
LOG_BUFFER_HARD_CAP = 5000   # 红色水位（100%）：驱逐后仍满则强制截断
```

### 3.2 日志等级驱逐优先级

驱逐顺序：**低价值先出，高价值保留**

```
优先驱逐（最低价值）   →   DEBUG
        ↓                  INFO
        ↓                  WARNING
最后驱逐（最高价值）   →   ERROR / CRITICAL
```

### 3.3 智能驱逐逻辑（伪代码）

```python
# log_action() 写入前的水位检测
async with self._buffer_lock:
    size = len(self._log_buffer)

    if size >= LOG_BUFFER_HARD_CAP:
        # 红色：按等级驱逐，保留 ERROR+ 日志
        self._log_buffer = _evict_by_level(self._log_buffer, keep_ratio=0.6)
        logger.error(f"[LogBuffer] 触达红色水位({size})，已按等级强制驱逐")

    elif size >= LOG_BUFFER_EVICT:
        # 橙色：驱逐 DEBUG/INFO 日志，为高优先级腾空间
        self._log_buffer = _evict_by_level(self._log_buffer, keep_ratio=0.8)
        logger.warning(f"[LogBuffer] 橙色水位({size})，驱逐低优日志中")
        asyncio.create_task(self.flush_logs())  # 同时触发紧急 flush

    elif size >= LOG_BUFFER_WARN:
        # 黄色：仅触发紧急 flush，不驱逐任何数据
        asyncio.create_task(self.flush_logs())
        logger.warning(f"[LogBuffer] 黄色水位({size})，已触发紧急 flush")

    self._log_buffer.append(log_entry)


def _evict_by_level(buffer: list, keep_ratio: float) -> list:
    """
    按日志等级智能驱逐。
    保留所有 ERROR/CRITICAL，从低优先级开始删除直到达到目标容量。
    """
    target_size = int(LOG_BUFFER_HARD_CAP * keep_ratio)
    if len(buffer) <= target_size:
        return buffer

    # 分桶
    HIGH   = [e for e in buffer if e.get("level") in ("ERROR", "CRITICAL")]
    MEDIUM = [e for e in buffer if e.get("level") == "WARNING"]
    LOW    = [e for e in buffer if e.get("level") in ("INFO", "DEBUG", None)]

    result = HIGH[:]  # ERROR/CRITICAL 全部保留
    remaining = target_size - len(result)

    # 先填 WARNING，再填 低优先级（都取最新的）
    result += MEDIUM[-remaining:] if remaining > 0 else []
    remaining = target_size - len(result)
    result += LOW[-remaining:] if remaining > 0 else []

    evicted = len(buffer) - len(result)
    logger.warning(f"[LogBuffer] 驱逐完成：丢弃 {evicted} 条低优日志，保留 {len(result)} 条")
    return result
```

### 3.4 Stats Buffer 防护（无驱逐，只 flush）

Stats 是累加值，**禁止任何丢弃**，只触发紧急排水：

```python
STATS_BUFFER_WARN = 5000    # 黄色：触发紧急 flush
STATS_BUFFER_CAP  = 10000   # 红色：同步阻塞 flush（不能 create_task）

if len(self._chat_stats_buffer) > STATS_BUFFER_CAP:
    # 红色水位：必须同步等待 flush 完成，确保数据不丢
    await self.flush_stats()
elif len(self._chat_stats_buffer) > STATS_BUFFER_WARN:
    asyncio.create_task(self.flush_stats())
```

---

## 4. BatchSink 重试设计

```python
# 重试协议
MAX_RETRY = 3
retry_count = item.get("_retry", 0)

if retry_count < MAX_RETRY:
    item["_retry"] = retry_count + 1
    await self._queue.put(item)   # 重新入队
else:
    logger.warning(f"[BatchSink] 任务 {item['id']} 重试超 {MAX_RETRY} 次，永久丢弃")
```

---

## 5. SQLite PRAGMA 配置

在 `core/db_init.py` 初始化连接后执行：

```sql
PRAGMA journal_mode = WAL;         -- 读写并发不互锁
PRAGMA synchronous = NORMAL;       -- 性能提升 3~5x，仍保留崩溃安全性
PRAGMA cache_size = -64000;        -- 64MB 共享页缓存
PRAGMA busy_timeout = 10000;       -- 等待 10s 后才报错，而非立即 OperationalError
PRAGMA wal_autocheckpoint = 1000;  -- 每 1000 页自动 checkpoint
```

---

## 6. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| flush 失败导致统计数据小量丢失 | 中 | 低 | 统计允许小量丢失，非核心路径 |
| 内存累加器 key 爆炸 | 低 | 高 | MAX_STATS_KEYS 上限 + 紧急 flush |
| WAL checkpoint 阻塞读 | 低 | 低 | wal_autocheckpoint=1000 分散压力 |
