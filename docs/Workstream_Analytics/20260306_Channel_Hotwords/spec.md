# 频道热词分析系统设计方案 (Channel Hotwords Analysis Spec)

## 1. 业务目标背景 (Context & Objectives)
旨在实现全盘文本采集分析，为每个频道以及全局构建实时与长期的热词榜单。支持自然日、月、年的时序级叠放归纳，并通过指令精确查询，支持全局每日定时推送。

**本方案针对指令要求："基于当前系统深度化，最大化复用worker" 进行了重构级优化设计。**

---

## 2. 深度架构设计与流转 (Deep Architecture Design)

在极致惰性执行(Ultra-Lazy Execution)和高内聚低耦合的架构规范下，系统拆分为以下三个核心分发段：

### 2.1 极简采集层 (Collection Layer): `HotwordMiddleware`
为了**绝对不阻塞**当前极速的 `Pipeline` 和事件循环：
- 在 `core/pipeline.py` 的执行流中，注入一个 `HotwordMiddleware`。
- 它只负责：判断消息是否为文本，抽取来源频道的**频道显示名称** (非ID) 和 **纯文本内容**。
- 将元数据推入内存 `asyncio.Queue` (或基于现有的缓冲器 `db_buffer`)，即刻 `return`，消耗不足 `0.1ms`。

### 2.2 NLP 加工作业层 (Processing & Worker Layer): `HotwordService`
最大化复用当前的异步 `WorkerService` 模型与线程池：
- 因为 `jieba` (分词算法) 与频分加权(TF-IDF/权频算子) 通常是 CPU 密集型的计算，**绝对禁止**直接在 Asyncio 的 Main Event Loop 中执行。
- **复用 Worker**：我们将热词提取封装为 `HotwordAnalysisTask`，提交给 `WorkerService` 中基于 `run_in_executor` 的线程池处理。在系统低峰期或达到阀值（如缓冲 50 条文本）时，触发批量(Batch) 分词。
- **精准度与降噪 (Accuracy & Noise Reduction)**:
    1. **词性过滤 (POS Filtering)**: 仅提取名词 (n)、人名 (nr)、地名 (ns)、机构名 (nt)、专有名词 (nz) 以及动词 (v)。自动过滤代词、连词、介词等垃圾信息。
    2. **三级停用词过滤 (Triple-Stopword Check)**:
       - **基础库**: 加载预置的 2000+ 通用中文停词表。
       - **自定义库**: 提供 `data/hot/user_stopwords.txt` 供用户手动屏蔽特定业务噪音词（如频道固定的小尾巴、广告词）。
       - **长度过滤**: 自动忽略单字词（如“的”、“了”、“我”），保留 2 字及以上的核心语义词。
    3. **热点发现与边界加权算法 (Advanced Hotspot Discovery)**:
       - **TF-IDF 动态权重 (Relative Burst)**: 词语在当前频道频率(TF)极高，且在全局(Global)频率较低时，判定为特有热点。
       - **突发脉冲增强 (Burst Boost)**: 在短时间内（如1小时内）词频增长率超过 300% 时，赋予该词 1.5x 的临时热度权重，确保瞬间爆发的新闻（如：突发地震、金融异动）能立即上榜，不受历史均值拖累。
       - **低频死信处理 (Low-Frequency Cull)**: 出现次数低于阈值（如：日均低于3次）的词，在归纳时不计入 `all.json`，防止几百个频道产生数百万个低频无效 Key 刺穿 512MB RAM。
       - **结构化特征降噪 (Structural Anti-Spam)**: 
           - **重复度惩罚**: 同一条长消息内重复出现 5 次以上的词（如刷屏广告），按 1 次计算。
           - **熵减过滤**: 词语如果仅在单一来源（如：同一个转发规则）出现，其全局热度权重按 0.5x 衰减，防止个别营销号自嗨式霸榜。
       - **多维级联衰减 (Cascade Decay)**: 
           - **日榜**: 权重 1.0。
           - **月榜**: `score = sum(day_score * 0.95^(today - day))`。
           - **年榜**: 采用半衰期算法，确保存量热词平滑淡出。

### 2.3 分布式存储落盘层 (Storage Layer) : `Local JSON Data Nodes`
遵循需求：独立文件记录，日、月、年逐级自动折叠，存储架构如下：
```text
/data
  /hot
    /全局总线 (Global)
       global_temp.json (实时缓冲期)
       global_all.json (全局全量热词累加)
       global_day_{YYYYMMDD}.json (全局日榜)
       global_month_{YYYYMM}.json (全局月榜)
       global_year_{YYYY}.json (全局年榜)
    /{频道名A}
       {频道名A}_temp.json (增量同步)
       {频道名A}_all.json (全量累加)
       {频道名A}_day_{YYYYMMDD}.json (独立日榜)
       {频道名A}_month_{YYYYMM}.json (独立月榜，保留至年终)
       {频道名A}_year_{YYYY}.json (年终归档)
    ...
```

---

## 3. 时序自动折叠逻辑 (Temporal Aggregation & Fold)

### 3.1 实时态 (`temp.json` -> `all.json`)
针对**好几百个频道**可能引发的“洪峰 IO”（例如1分钟内几百个文件全开写入），我们采取以下绝对防御：
- `temp.json` 的更新不是每个频道单独触发 IO 定时器。而是采用**全局异步聚合心跳 (Global Async Heartbeat)**。
- 维持一个大字典 `global_l1_cache: Dict[str, Counter]`。
- **批量下刷 (Batch Flush)**: 心跳触发时，直接在内存中异步、并行写入 Task。

### 3.2 自然日归纳 (Daily Rollup)
- **触发器**: 每天 `00:00:10`。
- **动作**: 将昨日 `temp` 数据固化为独立的 `day_{YYYYMMDD}.json`。

### 3.3 自然月/年归纳 (Monthly/Yearly Rollup)
- **月度生成**: 每月1号，扫描上月所有 `day` 文件，生成独立的 `month_{YYYYMM}.json`。**此时不进行年归纳，月文件单独留在频道文件夹下。**
- **年终密封 (Yearly Sealing)**:
  - **触发器**: 每年 1 月 1 日凌晨。
  - **动作**: 扫描过去 12 个月的 `month_*.json` 文件进行终极合并，生成 `year_{YYYY}.json`。
  - **物理清理**: 年归纳完成后，将这 12 个 `month` 文件移入 `archive/` 目录或直接删除，以维持频道根目录的检索效率。
- **慢熬策略 (Slow-Simmer Aggregation)**: 即使面对几百个频道，所有归纳动作均分拆为小任务，带 `1s` 间歇执行，确保 512MB RAM 无波动。

---

## 4. UI 与交互 (Frontend & Delivery)
摒弃繁杂交互，以结果为导向：
- **精准查询 (`/hot <频道名>`)**: 
  使用模糊匹配寻找 `/data/hot/` 下的文件夹名称，一旦匹配，返回该频道的热词日榜、月榜、总榜前10名组合图文/长文本视图。
- **大盘总览 (`/hot`)**: 
  如果未带参数，返回系统总频道热榜 (global)，让手机端更便捷！无需翻阅频道 ID！
- **定时推片 (`Daily Broadcaster`)**:
  借助 `sender_service.py` 和 TG 定时任务模块，在配置好的自然时间（如：每晚 20:00），将 `global` 区间的当日前10大热词推送到**指定配置的管理群或频道**。

## 5. 系统负载与内存安全机制 (System Load & Memory Guards)

为满足全站极其严苛的 **512MB CGroup (cgroups) 内存红线** 且保证极速并发处理的核心约束，系统必须采用最激进的内存降维打击：

### 5.1 RAM 锁死防线 (512MB 极限护航)
- **按需分配与微缩词典 (Micro-Dictionary & Lazy Initialization)**: `jieba` 引擎的标准加载会吃掉 80MB，这在 512MB 限制下极其昂贵。因此：
  1. 仅在首次触发分词 Batch 时惰性加载 (Lazy Load) `jieba`。
  2. 若内存极度紧张时（通过 `psutil` 探针发现快触顶 512MB），强制卸载内存中不活跃的 L1 频道统计并触发 `gc.collect()`。
  3. 剔除多余的辅助分词进程，只保持最简唯一的全局单例。
- **L1 极度压缩与秒刷 (Micro-Batch L1 Cache)**: 不能再容忍 10,000 个 Key 驻留内存。阈值下调为 **1,000 个 Key**，或者每 **60秒** 雷打不动地触发紧急落盘（Flush to Disk）。即使损失一点点 IO 性能，也绝不能让堆内存膨胀刺穿 512M!

### 5.2 CPU 与并行控制 (Zero CPU Starvation / IO Storm Prevention)
- **单线程微批下放 (Single-Thread Micro-Batch Offloading)**: 所有计算密集的 TF-IDF/词频过滤处理，只能放到 `WorkerService` 下属的一个 **唯一后台单线程** (Max Workers=1) 中排队执行。绝不允许多起几个线程同时跑 `jieba` 把内存翻倍！
- **抖动防潮 (Jitter Throttle)**: 大盘在每日 `00:00:10` 会面临几百个频道的聚合。我们不仅用流式 IO，更在频道与频道间强制触发强制垃圾回收 `gc.collect()` 和长达 `1000ms` 的休眠，把操作稀释到 1 小时内做完，对 VPS 的内存波动实现“心如止水”。

---

## 6. 项目落地技术栈引入 (Dependencies)
- `jieba`: 中文分词核心引擎 (限制为单例形态)。
- `aiofiles`: 异步 JSON 文件写入操作（保障 IO 安全）。
- `APScheduler`: 接入现存系统的自动归纳引擎。
