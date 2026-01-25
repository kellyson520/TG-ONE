# 技术方案：数据归档与冷存储集成 (Phase 3)

## 1. 背景
随着系统运行，`forward.db` (SQLite) 中的日志类数据（`rule_logs`, `rule_statistics` 等）会快速增长，导致主库查询变慢且维护成本增加。原先项目已具备基本的 Parquet 归档能力，本阶段目标是完整重构并衔接到新系统中，实现自动化的冷热数据分离。

## 2. 核心架构

### 2.1 存储分层
- **热数据 (Hot)**: 本地 SQLite `forward.db`，保留最近 30 天数据。
- **冷数据 (Cold)**: 本地/对象存储中的 Parquet 文件，按日期分区存储，永久或根据保留期限保存。

### 2.2 归档流程
1. **策略触发**: 每日凌晨或主库记录数超过阈值时触发。
2. **数据扫描**: 扫描主库中超过 30 天的记录。
3. **Parquet 转换**: 使用 `DuckDB` 将 SQL 记录转换为 `Parquet` 文件。
4. **Bloom 索引更新**: 更新 `Bloom Filter` 索引以支持快速全局查询（如去重检查）。
5. **主库清理**: 从主库删除已成功归档的数据，并执行 `VACUUM`。

## 3. 详细设计

### 3.1 归档管理器 (`ArchiveManager`)
位置：`utils/db/archive_manager.py` (New)
职责：
- 定义归档策略（哪些表、保留多久）。
- 执行 `main` 归档循环。
- 提供统一的查询入口（自动透明切换热/冷数据搜索）。

### 3.2 衔接原项目功能
- 复用 `utils/db/archive_store.py` (Parquet 读写)。
- 复用 `utils/db/bloom_index.py` (成员判定加速)。
- 适配新系统的 `SQLAlchemy` 模型。

### 3.3 数据一致性保证
- **事务性归档**: 只有在 Parquet 写入并校验成功后，才会删除主库数据。
- **防止重复**: 记录归档水位点（Watermark）或在 Parquet 写入时使用唯一文件名。

## 4. 接口设计

### 4.1 归档动作
```python
async def archive_table(table_name: str, days_threshold: int = 30):
    """归档指定表的数据"""
```

### 4.2 统一查询
```python
async def query_with_cold_storage(table_name: str, filters: dict, limit: int = 100):
    """先查主库，若不足则查 Parquet"""
```

## 5. 安全与运维
- 定期检查 `archive/` 目录磁盘占用。
- 支持 S3 远程存储扩展，避免本地磁盘资源耗尽。
