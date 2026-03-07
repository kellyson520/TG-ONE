# Hotword 性能危机 & 质量修复全量方案
**Task ID**: `20260306_Hotword_Perf_Crisis`
**时间**: 2026-03-06
**优先级**: P0 – 阻断级
**涵盖问题**:
1. 写延迟爆炸（9999999ms）/ 内存 90% 暴涨 → **性能危机**
2. 热榜充斥广告词 / 通用停用词 / 自适应学习失效 → **质量危机**

---

## 第一章：性能危机

### 1.1 问题现象

| 现象 | 具体表现 |
|---|---|
| 写延迟爆炸 | `flush_to_disk` 偶发 `9999999ms` 阻塞 |
| 内存占用 | 系统 RAM 90%，持续上涨无法回落 |
| 消息积压 | `HotwordCollector.queue` 打满、新消息被丢弃 |

### 1.2 根因诊断

#### 病因 A：全程持锁进行 DB I/O（死锁毒瘤）

```
flush_to_disk() 中：
  async with self._lock:            ← 锁在这里获取
      for channel in l1_cache:
          await repo.save_temp_counts(...)  ← 在锁内做 DB I/O（几百ms）
```

`process_batch()` 同样需要这把锁才能写 `l1_cache`，因此这段时间所有新消息处理全部被卡住。

#### 病因 B：伪批量写入（N 条 SQL 循环执行）

```python
# hotword_repo.py → save_temp_counts()
for word, meta in counts.items():        # 200 个词 → 200 次循环
    stmt = insert(HotRawStats).values(…)
    await session.execute(stmt)          # 每个词一次独立 IO 往返
await session.commit()
```

200 个词就是 200 次 SQLite WAL 写入，从而导致 IO 延迟从 10ms 飙升至 500ms+。

#### 病因 C：内存无底洞

写阻塞时间内，`l1_cache` 和 `user_hits` 持续积累新分词，jieba 线程池也在堆积任务，GC 无法回收，内存最终被撑至 90%。

### 1.3 修复方案

#### 修复 A：双缓冲（Double Buffering）释放锁 — `services/hotword_service.py`

核心思路：锁内只做**原子指针交换**（耗时 <1ms），锁外再做 DB 写入。

```python
@log_performance("刷写热词数据")
async def flush_to_disk(self):
    # ── 阶段1：原子换指针（持锁时间 <1ms）──────────────────────────
    async with self._lock:
        if not self.l1_cache and not self.noise_discovery_l1:
            return
        snapshot_cache = self.l1_cache
        snapshot_noise = self.noise_discovery_l1
        self.l1_cache = {}          # 立刻分配新对象，其他 process_batch 无阻塞
        self.noise_discovery_l1 = {}
    # ── 锁已释放，以下全是无竞争的 IO ────────────────────────────────

    # ── 阶段2：批量落盘（在锁外执行，耗时不影响主流程）──────────────
    for channel, stats in snapshot_cache.items():
        disk_data = {
            w: {"f": round(v["f"], 2), "u": v["u"]}
            for w, v in stats.items() if v["f"] >= 0.5
        }
        if disk_data:
            await self.repo.save_temp_counts(channel, disk_data)

    # ── 阶段3：自动学习（锁外，引用 snapshot_noise，原逻辑不变）──────
    if snapshot_noise:
        global_data = await self._load_period_data("global", "day")
        analyzer = await self.ensure_analyzer()
        new_noise_found = False
        current_noise = set(analyzer.noise_markers)
        for word, noise_count in snapshot_noise.items():
            if word in current_noise: continue
            if word in analyzer.white_list or word in analyzer.black_list: continue
            g_val = global_data.get(word, 0.0)
            g_freq = g_val.get("f", 0.0) if isinstance(g_val, dict) else float(g_val)
            total_count = g_freq + noise_count
            if total_count < 10: continue
            if noise_count / total_count > 0.7:
                current_noise.add(word)
                new_noise_found = True
        if new_noise_found:
            analyzer.noise_markers = current_noise
            await self.repo.save_config("noise", list(current_noise))

    logger.log_operation("热词数据落盘完成")
    gc.collect()
```

#### 修复 B：真正的 Bulk UPSERT — `repositories/hotword_repo.py`

```python
async def save_temp_counts(self, channel: str, counts: Dict[str, Dict[str, Any]]):
    if not counts:
        return

    rows = [
        {
            "channel": channel,
            "word": word,
            "score": meta.get("f", 0.0),
            "unique_users": meta.get("u", 0)
        }
        for word, meta in counts.items()
    ]

    async with self.session_factory() as session:
        try:
            stmt = insert(HotRawStats)
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=['channel', 'word'],
                set_={
                    "score": HotRawStats.score + stmt.excluded.score,
                    "unique_users": HotRawStats.unique_users + stmt.excluded.unique_users,
                }
            )
            await session.execute(upsert_stmt, rows)  # 单次批量执行，N词=1次IO
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Hotword DB Bulk Save Error ({channel}): {e}")
```

**性能提升**：200 词 → 500ms+ 降至 ~10ms。

---

## 第二章：热词质量危机

### 2.1 问题现象（实测榜单）

```
🥇 群组 (146次)   ← Telegram 平台通用停用词，毫无分析价值
🥉 冷漠 (69次)   ← 可疑，情绪词而非热点话题
🔹 广告 (17次)   ← 明显广告词，应被过滤
🔹 刷单 (28次)   ← 明显诈骗词，应被过滤
🔹 收款 (20次)   ← 明显诈骗词，应被过滤
🔹 群组/频道/交流/信息/发帖  ← 全部为 Telegram 结构性无意义词
```

### 2.2 根因诊断

#### 质量毒瘤 Q1：噪声消息中的词仍以 0.2 权重混入榜单

```python
# HotwordAnalyzer.analyze() 第 91-119 行
is_noise = any(marker in text for marker in self.noise_markers)
weight_multiplier = 0.2 if is_noise else 1.0   # ← 0.2 权重，但并非 0 ！

# ...
score = tf_idf_weight * cfg_weight * current_weight_multiplier
local_scores[word] = local_scores.get(word, 0.0) + score   # ← 仍然被累加进榜单！
```

**结论**：广告消息里的 `广告`、`刷单`、`收款` 虽然权重打了 0.2 折扣，但当消息量大时（如一天 100 条广告），累计分数仍然超越普通消息里出现 20 次的正常词，最终出现在榜单上。

#### 质量毒瘤 Q2：没有 Telegram 场景的停用词表

`群组`、`频道`、`交流`、`信息`、`视频`、`发帖`、`排行榜` 这类词：
- 在每个 Telegram 群/频道里**都存在**
- 对分析"今日热点"毫无意义
- jieba 默认词典没有将它们标记为停用词
- 项目的黑名单（`black_list`）为空或未含这些词

#### 质量毒瘤 Q3：自适应学习阈值过高，触发太慢

```python
if total_count < 10: continue     # ← 需要 10 次以上才触发学习
if noise_count / total_count > 0.7:  # ← 70% 才晋升噪声词
```

问题：
1. `total_count` 是 `g_freq（全局热词分数）+ noise_count（出现次数）`，这两者**量纲不同**（一个是 TF-IDF 分数，一个是计数），比较没有意义
2. 早期样本少时 noise_count < 10，广告词躲过了学习阶段，已经上榜了
3. 自动学习的结果只更新 `noise_markers`（触发标记词），不会反向清理已积累的 `l1_cache` 中的历史积分

### 2.3 修复方案

#### 修复 Q1：噪声消息完全不贡献分数 — `services/hotword_service.py`

```python
# HotwordAnalyzer.analyze() 修改逻辑

is_noise = any(marker in text for marker in self.noise_markers)

if is_noise:
    # 噪声消息不应对热词榜贡献任何分数
    # 只提取噪声候选词供自动学习使用
    noise_tags = self._jieba_tf_idf.extract_tags(
        text,
        topK=10,
        allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'v', 'vd', 'vn', 'a', 'ad', 'an', 'd')
    )
    for n_word in noise_tags:
        n_word = n_word.strip()
        if len(n_word) < 2: continue
        if n_word in self.white_list: continue
        noise_candidates[n_word] = noise_candidates.get(n_word, 0) + 1
    continue  # ← 直接跳过，不进入热词评分逻辑！

# 非噪声消息才进行 TF-IDF 评分
words_with_weights = self._jieba_tf_idf.extract_tags(...)
for word, tf_idf_weight in words_with_weights:
    ...
```

#### 修复 Q2：内置 Telegram 场景停用词表 — `services/hotword_service.py`

在 `HotwordAnalyzer.__init__()` 中内置一个不可修改的 Telegram 平台停用词集合：

```python
# 不依赖外部配置，硬编码 Telegram 场景下永远无意义的高频词
# 这些词在任何 TG 群/频道都高频出现，不代表任何热点
self._tg_stopwords: Set[str] = {
    # 平台结构词
    '群组', '频道', '群聊', '频道名', '消息', '通知', '置顶', '公告',
    '机器人', '管理员', '管理', '用户', '成员',
    # 通用动作词
    '发帖', '转发', '分享', '点击', '链接', '加入', '订阅', '关注',
    '交流', '讨论', '问题', '回复', '评论', '发送',
    # 通用描述词
    '信息', '内容', '视频', '图片', '文件', '资源',
    '最新', '今日', '每日', '每天', '今天', '时间',
    '排行榜', '榜单', '推荐', '热门', '精选',
    # 数字表达
    '第一', '最大', '最多',
}

def _is_tg_stopword(self, word: str) -> bool:
    return word in self._tg_stopwords
```

在 `analyze()` 的词循环中加入过滤：

```python
for word, tf_idf_weight in words_with_weights:
    word = word.strip()
    if len(word) < 2: continue
    if word in msg_keywords: continue
    if word in self.black_list: continue
    if self._is_tg_stopword(word): continue   # ← 新增：跳过平台停用词
    msg_keywords.add(word)
    ...
```

#### 修复 Q3：自适应学习算法重写 — `services/hotword_service.py`

问题：量纲混淆 + 阈值太高。

```python
# flush_to_disk() 中，自动学习部分重写：

for word, noise_count in snapshot_noise.items():
    if word in current_noise: continue
    if word in analyzer.white_list or word in analyzer.black_list: continue
    if analyzer._is_tg_stopword(word): continue    # ← 停用词也不需要学习

    # 修复量纲问题：改为只使用次数比较，不与 TF-IDF 分数混算
    # 从 snapshot_cache 中获取该词在非噪声消息里的出现情况
    global_count_in_normal = sum(
        v.get("u", 0)  # 使用 unique_users 计数，量纲一致
        for ch_stats in snapshot_cache.values()
        for w, v in ch_stats.items()
        if w == word
    )

    total_count = global_count_in_normal + noise_count
    if total_count < 5: continue    # ← 降低门槛至 5 次（原来 10 次太慢）

    noise_ratio = noise_count / total_count
    if noise_ratio > 0.6:           # ← 降低阈值至 60%（原来 70% 太严格）
        logger.info(f"Auto-learned noise marker: '{word}' (ratio={noise_ratio:.2f}, noise={noise_count}, normal={global_count_in_normal})")
        current_noise.add(word)
        new_noise_found = True
```

---

## 3. 变更范围总览

| 文件 | 变更点 | 修复内容 | 优先级 |
|---|---|---|---|
| `services/hotword_service.py` | `flush_to_disk()` | 双缓冲+锁外IO | **P0** |
| `services/hotword_service.py` | `HotwordAnalyzer.__init__()` | 内置 TG 停用词表 | **P0** |
| `services/hotword_service.py` | `HotwordAnalyzer.analyze()` | 噪声消息完全不贡献分数 | **P0** |
| `services/hotword_service.py` | 自动学习逻辑（flush_to_disk 内） | 量纲修正 + 降低阈值 | **P0** |
| `repositories/hotword_repo.py` | `save_temp_counts()` | 真 Bulk UPSERT | **P0** |
| `middlewares/hotword.py` | `_extract_text()` | 防洪截断 2000 字 | P1 |

---

## 4. 预期效果对比

| 指标 | 修改前 | 修改后（预期）|
|---|---|---|
| 延迟峰值 | 9999999ms（死锁）| <1ms（原子交换解锁）|
| DB 写入耗时（200词）| ~500ms（N次往返）| ~10ms（1次批量）|
| 内存趋势 | 持续上涨至 90% | GC 正常，低水位稳定 |
| 广告词/诈骗词上榜 | 必现（0.2权重仍累积）| 完全隔离，不贡献分数 |
| TG 通用停用词上榜 | 必现（无过滤）| 全部过滤 |
| 自动学习生效速度 | 需 10 次样本 + 70% 比例 | 5 次样本 + 60% 比例 |

---

## 5. 验证方案

修改后运行集成测试：
```powershell
$env:PYTHONPATH='e:\重构\TG ONE'
python tests/integration/test_hotword_v2.py
```

榜单质量验收标准（人工目测）：
- [ ] `群组`、`频道`、`交流`、`信息`、`发帖` 等通用词不出现在 Top 15
- [ ] `广告`、`刷单`、`收款` 等诈骗词不出现在 Top 15
- [ ] Top 15 中出现具体话题性名词（如 `国漫`、`追番`、`新剧` 等）

性能验收标准（日志观察）：
- [ ] 无 `Hotword queue full` 告警
- [ ] 无 `9999999ms` 耗时日志
- [ ] `Auto-learned noise marker` 日志在运行 5 分钟内出现（说明学习系统生效）

---
**Implementation Plan, Task List and Thought in Chinese**
