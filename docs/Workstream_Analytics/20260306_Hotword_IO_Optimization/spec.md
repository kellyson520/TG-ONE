# Hotword IO Optimization (热词 IO 削峰填谷优化)

## 1. 业务背景 (Context)
热词分析系统在处理大量频道时，会产生数千个文件夹和小文件（`temp.json`）。在聚合阶段（每日/每月）会由于高并发的文件创建与写入导致 IO 阻塞、内存抖动以及系统响应延迟。

## 2. 核心瓶颈 (Bottlenecks)
- **Inode 爆炸**：大量小文件夹和小文件对 NTFS/EXT4 文件系统的压力。
- **并发写冲突**：聚合期间全量频道同时触发 IO 操作。
- **内存压力**：JSON 频繁序列化/反序列化占用堆内存。

## 3. 技术方案 (Technical Proposal)

### 方案 A：受控并发与延迟 IO (Semaphore Control) - 首选低成本方案
- **IO 信号量**：在 `HotwordService` 中引入 `asyncio.Semaphore`，全局限制同时处理的频道数。
- **批处理抖动 (Jitter)**：在循环中加入随机休眠，避免所有频道在同一秒开始聚合。
- **惰性目录创建**：仅在命中 L1 缓冲区刷新且目录不存在时执行 `mkdir`。

### 方案 B：核心数据库持久化 (hotwords.db) - **正式实施路径**
- **存储位置**：`data/db/hotwords.db`。采用独立库设计，避免与业务库 `forward.db` 竞争锁。
- **性能模式**：
  - **WAL 模式**：读写不互斥。
  - **Synchronous = NORMAL**：平衡安全性与极致写入性能（聚合阶段性能提升约 3-5 倍）。
  - **MMAP**：开启 128MB 内存映射，减少热点词查询的系统调用。
- **表结构设计**：
  - `hot_raw_stats`: 存储临时增量（替代原来的 `temp.json`）。
    ```sql
    CREATE TABLE hot_raw_stats (
        channel TEXT,
        word TEXT,
        score REAL DEFAULT 0.0,
        unique_users INTEGER DEFAULT 0,
        last_update TIMESTAMP,
        PRIMARY KEY(channel, word)
    );
    ```
  - `hot_period_stats`: 存储归档的历史榜单（day/month/year）。
    ```sql
    CREATE TABLE hot_period_stats (
        channel TEXT,
        word TEXT,
        period TEXT, -- 'day', 'month', 'year'
        date_key TEXT, -- e.g., '20260306'
        score REAL,
        user_count INTEGER,
        PRIMARY KEY(channel, word, period, date_key)
    );
    CREATE INDEX idx_period_date ON hot_period_stats(period, date_key);
    ```
  - `hot_config`: 存储黑/白名单及噪声特征库。

### 方案 C：IO 削峰策略 (流量门禁)
- **聚合信号量**：处理大规模频道（>100个）的归档任务时，使用 `asyncio.Semaphore(10)`。
- **事务合并**：聚合脚本不再逐个词写入，而是按频道开启 `BEGIN IMMEDIATE` 批处理事务。

## 4. 架构变动 (Architectural Changes)
- **Repository 层**：完全重写 `HotwordRepository`，移除 `aiofiles` JSON 逻辑，接入 SQLAlchemy 或高性能异步 SQLite 驱动。
- **Service 层**：`flush_to_disk` 改为数据库 `UPSERT` 操作，`load_rankings` 改为 SQL 分页查询。

## 5. 质量指标 (Quality Gate)
- **内存限制**：任务运行期间 RAM 增量不得超过 512MB。
- **IO 响应**：系统 CPU `iowait` 均值低于 15%。
- **稳定性**：聚合过程中不应出现 `OSError: Too many open files`。
