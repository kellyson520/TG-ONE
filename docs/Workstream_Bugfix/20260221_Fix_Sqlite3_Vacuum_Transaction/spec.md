# 技术方案: 修复 SQLite3 VACUUM 事务冲突

## 背景
SQLite 的 `VACUUM` 命令不能在事务块（transaction block）中执行。
在 SQLAlchemy 2.0 中，`connection.connect()` 可能默认启用自动开始事务的行为。
即使设置了 `isolation_level="AUTOCOMMIT"`，如果有事件监听器（如 `do_begin_immediate`）强制发送 `BEGIN IMMEDIATE`，也可能导致冲突。

## 方案设计

### 1. 同步实现优化
目前的同步实现：
```python
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    conn.execute(text("VACUUM"))
```
这种写法通常是正确的，但如果 `connect` 层面就触发了 `begin` 事件，可能会有问题。

### 2. 异步实现优化
目前的异步实现：
```python
async with engine.connect() as conn:
    conn = conn.execution_options(isolation_level="AUTOCOMMIT")
    await conn.execute(text("VACUUM"))
```
由于 `engine.connect()` 已经在 context manager 开启时获取了连接，设置 `execution_options` 可能需要更早或者重新获取 connection。

更可靠的方法是使用 `engine.execution_options(isolation_level="AUTOCOMMIT").connect()`。

### 3. 拦截事务监听器
在 `sqlite_config.py` 中，我们有一个 `do_begin_immediate` 监听器：
```python
@event.listens_for(target_engine, "begin")
def do_begin_immediate(conn):
    conn.exec_driver_sql("BEGIN IMMEDIATE")
```
当 `isolation_level="AUTOCOMMIT"` 时，SQLAlchemy **不应该**触发 `begin` 事件。如果它触发了，说明逻辑上有问题。

## 实施步骤
1. 修改 `core/db_factory.py`:
   - 使用 `engine.execution_options(isolation_level="AUTOCOMMIT").connect()` 确保整个连接生命周期处于 AUTOCOMMIT。
   - 显式调用 `conn.rollback()` 或确保连接干净。
2. 验证测试。
