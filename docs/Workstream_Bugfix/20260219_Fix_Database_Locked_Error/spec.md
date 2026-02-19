# 技术方案: SQLite 数据库锁定深度治理

## 1. 背景与问题分析
当前系统使用 SQLite 作为数据存储，虽然启用了 WAL 模式，但在高并发写入（如任务队列更新、统计数据持久化）时，仍会出现 `database is locked` 错误。

### 1.1 根本原因
SQLite 的默认事务行为是 `DEFERRED`。这意味着事务开始时只获取 `SHARED` 锁，当执行第一个写操作时，才尝试升级为 `RESERVED` 锁，最后升级为 `EXCLUSIVE` 锁。
如果有两个连接都持有了 `SHARED` 锁并想升级为 `RESERVED` 锁，就会发生死锁或锁定错误。

### 1.2 解决方案
强制在事务开始时执行 `BEGIN IMMEDIATE`。这将立即尝试获取 `RESERVED` 锁，如果失败则等待 `busy_timeout`。这保证了在写操作开始前就已经排除了其他潜在的冲突写者。

## 2. 实施细节

### 2.1 启用 `BEGIN IMMEDIATE`
在 SQLAlchemy 中，通过监听连接事件并执行 `BEGIN IMMEDIATE` 来实现。

```python
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    # ... 其他 PRAGMA
    cursor.close()

@event.listens_for(engine.sync_engine, "begin")
def do_begin_immediate(conn):
    conn.exec_driver_sql("BEGIN IMMEDIATE")
```

注意：对于 `aiosqlite`，我们需要特别处理，因为它是异步的，但 SQLAlchemy 的 `sync_engine` 事件在一定程度上可以处理。

### 2.2 统一配置
将 `core/database.py` 和 `core/db_factory.py` 中的 PRAGMA 设置逻辑提取为通用函数。

### 2.3 增强重试装饰器
修改 `core/helpers/db_utils.py` 中的 `async_db_retry`：
- 添加 `func.__name__` 到日志中。
- 增加重试次数或优化退避间隔。

## 3. 并发测试策略
使用 `asyncio.gather` 模拟多个协程同时进行 `complete` 操作，验证在高竞争下是否能稳定工作。
