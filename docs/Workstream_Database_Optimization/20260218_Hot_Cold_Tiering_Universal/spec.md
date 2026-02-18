# 数据库存储架构优化：通用热冷分层方案

## 📋 项目概述

**目标**: 解决数据库膨胀问题（当前 144MB），通过建立统一的热冷分层架构，实现空间压缩、性能优化和无限历史记录能力。

**核心原则**: 
- **极致复用**: 一套代码支持所有表的自动归档
- **透明查询**: Web 端无感知地查询热库+冷库
- **零停机**: 不影响现有业务运行

---

## 🎯 核心目标

### 1. 空间优化目标
- **当前状态**: `forward.db` = 144MB (其中 `task_queue` 占 ~140MB, 234,033 条记录)
- **目标状态**: `forward.db` < 10MB (仅保留最近 7-30 天热数据)
- **压缩率**: 通过 Parquet + ZSTD 压缩，预计整体压缩率 > 90%

### 2. 性能优化目标
- **查询性能**: 历史数据查询从秒级降至毫秒级 (Parquet 列式存储优势)
- **写入性能**: 热库保持轻量，INSERT 性能不受历史数据影响
- **存储成本**: 冷数据存储成本降低 90%+

### 3. 可扩展性目标
- **通用化**: 支持任意表的自动热冷分层 (TaskQueue, RuleLog, AuditLog, MediaSignature 等)
- **配置化**: 通过 `.env` 统一控制各表的保留策略
- **自动化**: 每日自动执行归档，无需人工干预

---

## 🏗️ 架构设计

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    应用层 (Services/Web)                     │
│                  TaskService / AnalyticsService              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              统一查询桥 (UnifiedQueryBridge)                 │
│         自动路由到热库或冷库，合并结果返回                    │
└───────────┬─────────────────────────────────┬───────────────┘
            │                                 │
            ▼                                 ▼
┌───────────────────────┐         ┌──────────────────────────┐
│   热数据层 (Hot)       │         │   冷数据层 (Cold)         │
│   SQLite (forward.db) │         │   Parquet (archive/)     │
│   - 最近 7-30 天       │         │   - 历史数据              │
│   - 高频读写           │         │   - 列式存储 + ZSTD      │
│   - 快速查询           │         │   - DuckDB 查询引擎      │
└───────────────────────┘         └──────────────────────────┘
```

### 三层架构详解

#### A. 热数据层 (Hot Region - SQLite)
**职责**: 存储最近的活跃数据
- **存储引擎**: SQLite + WAL 模式
- **数据范围**: 
  - `task_queue`: 最近 7 天
  - `rule_logs`: 最近 30 天
  - `audit_logs`: 最近 30 天
  - `media_signatures`: 最近 60 天
- **特点**: 
  - 频繁读写
  - 低延迟查询 (< 10ms)
  - 支持事务 ACID

#### B. 冷数据层 (Cold Region - Parquet)
**职责**: 长期归档历史数据
- **存储格式**: Apache Parquet (列式存储)
- **压缩算法**: ZSTD (压缩率 > 90%)
- **分区策略**: 按日期分区 `year=YYYY/month=MM/day=DD`
- **存储位置**: `data/archive/parquet/{table_name}/`
- **特点**:
  - 极致压缩
  - 高效范围查询
  - 不可变存储 (Immutable)

#### C. 统一查询层 (Unified Query Bridge)
**职责**: 透明化热冷数据访问
- **查询引擎**: DuckDB (嵌入式 OLAP)
- **核心逻辑**:
  ```sql
  -- 自动合并热库和冷库数据
  SELECT * FROM sqlite_scan('forward.db', 'task_queue') 
  WHERE created_at > date('now', '-7 days')
  UNION ALL
  SELECT * FROM read_parquet('archive/task_queue/**/*.parquet')
  WHERE created_at <= date('now', '-7 days')
  ORDER BY id DESC LIMIT 50
  ```
- **优化策略**:
  - 优先查询热库 (大部分查询命中热数据)
  - 按需加载冷库 (仅在需要历史数据时)
  - 谓词下推 (Predicate Pushdown) 减少数据扫描

---

## 🔧 技术实现方案

### 1. 通用归档引擎 (`core/archive/engine.py`)

**核心类**: `UniversalArchiver`

**功能**:
- 自动识别模型字段并转换为 Parquet Schema
- 批量读取过期数据 (基于 `created_at` 或 `updated_at`)
- 事务性写入 Parquet + 删除 SQLite 记录
- 支持增量归档和全量归档

**关键方法**:
```python
class UniversalArchiver:
    async def archive_table(
        self, 
        model_class: Type[Base],  # SQLAlchemy 模型
        hot_days: int,             # 热数据保留天数
        batch_size: int = 10000    # 批量处理大小
    ) -> ArchiveResult
```

**复用点**:
- 通过反射自动获取模型字段，无需硬编码
- 统一的事务管理和错误处理
- 可配置的批量大小和并发度

### 2. 统一查询桥 (`core/archive/bridge.py`)

**核心类**: `UnifiedQueryBridge`

**功能**:
- 拦截 Repository 查询请求
- 智能路由到热库或冷库
- 自动合并结果集

**关键方法**:
```python
class UnifiedQueryBridge:
    async def query(
        self,
        model_class: Type[Base],
        filters: Dict[str, Any],
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]
```

**查询策略**:
1. **热优先**: 先查询 SQLite，如果结果充足则直接返回
2. **冷补充**: 如果热库结果不足 `limit`，则查询 Parquet 补充
3. **智能缓存**: 对冷库查询结果进行短期缓存 (5 分钟)

### 3. 自动化任务调度 (`services/db_maintenance_service.py`)

**注册表配置**:
```python
# 统一注册表：一行配置实现一个表的自动归档
ARCHIVE_REGISTRY = {
    TaskQueue: {
        'hot_days': settings.HOT_DAYS_LOG,      # 7 天
        'enabled': True,
        'priority': 1  # 优先级最高
    },
    RuleLog: {
        'hot_days': settings.HOT_DAYS_LOG,      # 30 天
        'enabled': True,
        'priority': 2
    },
    AuditLog: {
        'hot_days': settings.HOT_DAYS_LOG,      # 30 天
        'enabled': True,
        'priority': 3
    },
    MediaSignature: {
        'hot_days': settings.HOT_DAYS_SIGN,     # 60 天
        'enabled': True,
        'priority': 4
    }
}
```

**自动化流程**:
1. 每日凌晨 3:30 触发 (由 `CLEANUP_CRON_TIMES` 控制)
2. 按优先级顺序执行各表归档
3. 归档完成后执行 `VACUUM` 回收空间
4. 记录归档统计并推送通知

---

## 📊 数据流转流程

### 归档流程 (Archive Flow)

```
1. [触发] 定时任务或手动触发
   ↓
2. [扫描] 识别超过 hot_days 的记录
   ↓
3. [读取] 批量读取过期数据 (10,000 条/批)
   ↓
4. [转换] SQLAlchemy ORM → Dict → Parquet Schema
   ↓
5. [写入] 写入 Parquet 文件 (按日期分区)
   ↓
6. [验证] 校验 Parquet 文件完整性
   ↓
7. [删除] 事务性删除 SQLite 中的对应记录
   ↓
8. [提交] 提交事务，完成归档
   ↓
9. [清理] 执行 VACUUM 回收物理空间
```

### 查询流程 (Query Flow)

```
1. [请求] Web 端发起查询 (如: 获取最近 100 条任务)
   ↓
2. [路由] UnifiedQueryBridge 拦截请求
   ↓
3. [热查] 查询 SQLite 热库
   ↓
4. [判断] 结果数量是否满足 limit?
   ├─ 是 → 直接返回
   └─ 否 → 继续查询冷库
   ↓
5. [冷查] DuckDB 查询 Parquet 冷库
   ↓
6. [合并] 合并热库 + 冷库结果
   ↓
7. [返回] 返回统一结果集给 Web 端
```

---

## 🛡️ 风险控制与回滚策略

### 1. 数据安全保障
- **备份优先**: 归档前自动备份 SQLite 文件
- **事务保护**: 归档操作在事务中进行，失败自动回滚
- **校验机制**: 写入 Parquet 后校验记录数和关键字段
- **双写期**: 归档后保留 SQLite 记录 24 小时，验证无误后再删除

### 2. 性能保障
- **批量处理**: 避免单次处理过多数据导致内存溢出
- **限流控制**: 归档任务限制 CPU 和内存使用
- **错误隔离**: 单表归档失败不影响其他表

### 3. 回滚方案
- **紧急回滚**: 从备份文件恢复 SQLite
- **数据恢复**: 从 Parquet 文件反向导入 SQLite
- **降级开关**: 通过配置关闭归档功能，恢复纯 SQLite 模式

---

## 📈 预期收益

### 空间收益
| 项目 | 当前 | 优化后 | 节省 |
|------|------|--------|------|
| SQLite 大小 | 144 MB | < 10 MB | 93% |
| 总存储空间 | 144 MB | ~20 MB | 86% |
| 备份时间 | ~5 秒 | < 1 秒 | 80% |

### 性能收益
| 指标 | 当前 | 优化后 | 提升 |
|------|------|--------|------|
| 热数据查询 | 50-100ms | 5-10ms | 10x |
| 历史数据查询 | 500-1000ms | 50-100ms | 10x |
| 写入性能 | 正常 | 提升 20% | - |

### 运维收益
- **自动化**: 无需手动清理数据
- **可观测**: 归档统计和监控
- **可扩展**: 新表一行配置即可接入

---

## 🔄 与现有系统的兼容性

### 不需要修改的部分
- ✅ SQLAlchemy 模型定义
- ✅ 现有的 Repository 接口
- ✅ Web 端 API 接口
- ✅ 前端查询逻辑

### 需要增强的部分
- 🔧 `TaskService.list_tasks`: 接入 UnifiedQueryBridge
- 🔧 `AnalyticsService`: 支持跨热冷库统计
- 🔧 `DBMaintenanceService`: 添加归档任务调度

---

## 📝 配置项说明

### 新增环境变量 (`.env`)

```env
# === 热冷分层配置 ===
# 是否启用自动归档
AUTO_ARCHIVE_ENABLED=true

# 各表热数据保留天数
HOT_DAYS_TASK=7        # TaskQueue 保留 7 天
HOT_DAYS_LOG=30        # RuleLog/AuditLog 保留 30 天
HOT_DAYS_SIGN=60       # MediaSignature 保留 60 天
HOT_DAYS_STATS=180     # 统计数据保留 180 天

# 归档批量大小
ARCHIVE_BATCH_SIZE=10000

# 归档并发度
ARCHIVE_MAX_WORKERS=2

# DuckDB 内存限制
DUCKDB_MEMORY_LIMIT=2GB

# 是否启用查询缓存
ARCHIVE_QUERY_CACHE_ENABLED=true
ARCHIVE_QUERY_CACHE_TTL=300  # 5 分钟
```

---

## 🎯 成功标准

### 功能验证
- [ ] 归档任务能正常执行，无错误日志
- [ ] Web 端查询历史任务，结果正确完整
- [ ] 数据库大小降至 < 10MB
- [ ] Parquet 文件正确生成并可查询

### 性能验证
- [ ] 热数据查询延迟 < 10ms
- [ ] 历史数据查询延迟 < 100ms
- [ ] 归档任务执行时间 < 5 分钟

### 稳定性验证
- [ ] 连续运行 7 天无异常
- [ ] 数据一致性校验通过
- [ ] 备份恢复流程验证通过

---

## 📚 参考资料

- [Apache Parquet 官方文档](https://parquet.apache.org/)
- [DuckDB 文档](https://duckdb.org/docs/)
- [SQLAlchemy 反射机制](https://docs.sqlalchemy.org/en/20/core/reflection.html)
- [热冷分层最佳实践 (AWS)](https://aws.amazon.com/blogs/database/implementing-a-data-lake-architecture/)
