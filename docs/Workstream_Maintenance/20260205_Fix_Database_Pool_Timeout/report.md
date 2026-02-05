"""
数据库连接池超时问题修复报告
=====================================

## 问题描述

错误信息：
```
QueuePool limit of size 1 overflow 0 reached, connection timed out, timeout 60.00
```

## 根本原因

在 `core/db_factory.py` 中，写引擎的连接池配置被硬编码为：
- pool_size=1  # 只有1个连接
- max_overflow=0  # 不允许溢出

这导致在并发场景下（如批量写入任务），多个操作竞争同一个连接，
超过60秒后触发 TimeoutError。

## 修复方案

### 1. 修复 db_factory.py 写引擎配置

**文件**: `core/db_factory.py`
**行数**: 89-97

**修改前**:
```python
cls._async_write_engine = create_async_engine(
    db_url,
    pool_size=1,  # Single writer
    max_overflow=0,
    pool_timeout=60,
    ...
)
```

**修改后**:
```python
cls._async_write_engine = create_async_engine(
    db_url,
    pool_size=settings.DB_POOL_SIZE,  # 使用配置的连接池大小
    max_overflow=settings.DB_MAX_OVERFLOW,  # 使用配置的溢出连接数
    pool_timeout=settings.DB_POOL_TIMEOUT,
    ...
)
```

### 2. 修复 database.py 中的硬编码配置

**文件**: `core/database.py`
**行数**: 28-34

**修改前**:
```python
self.engine = create_async_engine(
    db_url, 
    echo=False,
    connect_args=connect_args,
    pool_size=20,  # 硬编码
    max_overflow=10  # 硬编码
)
```

**修改后**:
```python
from core.config import settings

self.engine = create_async_engine(
    db_url, 
    echo=False,
    connect_args=connect_args,
    pool_size=settings.DB_POOL_SIZE,  # 使用配置
    max_overflow=settings.DB_MAX_OVERFLOW  # 使用配置
)
```

## 配置值

从 `core/config/__init__.py` 中读取的默认值：
- DB_POOL_SIZE: 20
- DB_MAX_OVERFLOW: 30
- DB_POOL_TIMEOUT: 30 (秒)
- DB_POOL_RECYCLE: 3600 (秒)

## 影响范围

### 受影响的组件
1. ✅ TaskRepository.push_batch() - 批量任务写入
2. ✅ 所有使用 container.db 的服务
3. ✅ Web Admin API 的数据库操作
4. ✅ Worker 并发任务处理

### 不受影响的组件
- 读引擎 (readonly=True) - 已经正确使用了 settings 配置
- 测试环境 - 使用内存数据库

## 验证方法

运行以下命令验证修复：
```bash
python -c "from core.db_factory import DbFactory; from core.config import settings; engine = DbFactory.get_async_engine(readonly=False); print(f'✅ Pool Size: {engine.pool.size()}'); print(f'✅ Max Overflow: {engine.pool.overflow()}'); assert engine.pool.size() == settings.DB_POOL_SIZE, 'Pool size mismatch!'"
```

预期输出：
```
✅ Pool Size: 20
✅ Max Overflow: 30
```

## 预期效果

修复后，系统将能够：
1. ✅ 支持最多 20 个并发数据库连接
2. ✅ 在高峰期允许额外 30 个溢出连接
3. ✅ 避免连接池耗尽导致的 TimeoutError
4. ✅ 提升批量操作的性能和稳定性

## 注意事项

### SQLite 并发限制
虽然增加了连接池大小，但 SQLite 本身的并发写入能力有限：
- 已启用 WAL 模式 (Write-Ahead Logging)
- 支持多读单写
- 连接池主要用于读操作和短暂的写操作排队

### 生产环境建议
如果需要更高的并发写入性能，建议：
1. 迁移到 PostgreSQL 或 MySQL
2. 使用消息队列缓冲写入请求
3. 实施批量提交策略（已在 TaskRepository.push_batch 中实现）

## 修复时间
2026-02-05 11:17

## 修复人员
AI Assistant (Antigravity)
"""
