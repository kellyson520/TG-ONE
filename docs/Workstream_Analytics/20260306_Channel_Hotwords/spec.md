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
- **频分加权算法**：过滤无意义动词/副词/英文符号（加载停用词表 `stopwords.txt`）。基于出现频率叠加时间衰减(如适用)统计核心名词，生成权重 `{"keyword": weight}`。

### 2.3 分布式存储落盘层 (Storage Layer): `Local JSON Data Nodes`
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
       {频道名A}_temp.json (每分钟增量同步)
       {频道名A}_all.json
       {频道名A}_day_{YYYYMMDD}.json
       {频道名A}_month_{YYYYMM}.json
       {频道名A}_year_{YYYY}.json
    ...
```

---

## 3. 时序自动折叠逻辑 (Temporal Aggregation & Fold)

### 3.1 实时态 (`temp.json` -> `all.json`)
针对**好几百个频道**可能引发的“洪峰 IO”（例如1分钟内几百个文件全开写入），我们采取以下绝对防御：
- `temp.json` 的更新不是每个频道单独触发 IO 定时器。而是采用**全局异步聚合心跳 (Global Async Heartbeat)**。
- 维持一个大字典 `global_l1_cache: Dict[str, Counter]`。
- **批量下刷 (Batch Flush)**: 心跳触发时，将这个全局字典中有更新的频道，一次性包装为多个 `aiofiles` 的异步写入 Tasks。这样能够把对数百个 `temp.json` 的修改并行交给操作系统的 VFS (虚拟文件系统)，而绝不存在上百个 Python 文件句柄互锁导致的卡死。由于是 `asyncio.gather` 并发写，总耗时会被压缩到极致的几十毫秒级别。

### 3.2 自然日归纳 (Daily Rollup)
- **触发器**: Scheduler 服务每天 `00:00:10` 执行。
- **动作**: 
  1. 将昨天积攒的 `{频道}_temp.json` 与 `global_temp.json` 重命名为 `{频道}_day_{昨天日期}.json`。
  2. 清空重新生成当天的 `temp.json`。
  3. 触发**全频道总榜聚合**，同时更新总榜和各个频道的 `all.json` 累加库。

### 3.3 自然月/年归纳 (Monthly/Yearly Rollup)
- **触发器**: Scheduler 服务每月1号 / 每年1月1号 执行。
- **慢熬策略 (Slow-Simmer Aggregation)**: 由于面对的是**几百个**频道的历史文件夹，绝不支持在一个函数里使用 `for folder in channels` 直接去扫！这会拉高 VPS 瞬间的 CPU 和内存占用。
  1. 归纳动作被拆分为 Task，抛入后台队列慢慢消费。
  2. 加入类似 300ms ~ 1000ms 的间歇。
  3. 即使 500 个频道需要花半小时才折叠完，对系统也完全是一种“温柔流产”，VPS负载监控甚至感受不到波动。
- **动作**:
  1. 扫描上个月所有的 `day_{YYYYMMDD}.json`，流式迭代读取对应频道数据合并 `Counter`，加权生成 `month_{YYYYMM}.json`。
  2. 同理自动将 12 个 `month` 合并生成 `year_{YYYY}.json`。
  3. 执行存储瘦身：对于已经成功归纳的 `day` 文件，使用 `shutil.rmtree` 或打包归档剔除，阻止文件句柄超限及零散文件拖慢操作系统目录遍历速度。

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
