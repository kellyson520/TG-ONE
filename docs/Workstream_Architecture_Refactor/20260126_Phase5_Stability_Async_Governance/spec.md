# Technical Specification: Phase 5 Stability & Async Governance

## 1. 异常处理标准 (Error Handling Standard)
所有异常捕获必须遵循：
```python
try:
    ...
except Exception as e:
    logger.exception(f"Component Error: {e}", extra={"context": "..."})
    # 或者对于非关键路径
    logger.warning(f"Feature degradation: {e}")
```
严禁使用 `except:`。

## 2. 异步合规性 (Async Compliance)
- **HTTP Client**: 统一使用 `httpx.AsyncClient`。
- **Event Loop**: 使用 `asyncio.create_task` 或 `asyncio.gather` 处理并发，严禁在异步函数中调用同步阻塞函数（如 `requests.get`）。
- **Loop 获取**: 统一使用 `asyncio.get_running_loop()`，并在 `Container` 生命周期中管理。

## 3. Session 架构 (Session Architecture)
- **New Service**: `SessionService` 负责 Telethon Session 文件的状态维护。
- **Logic**:
    - `load_session()`: 异步加载并同步数据库状态。
    - `reconnect_all()`: 异步重连丢失的会话。
    - `health_check()`: 定期验证会话有效性。

## 4. 守护服务 (Guardian Services)
- `GuardService` 将成为系统唯一的后台任务协调者。
- 任务包括：
    - `MemoryGuard`: 监控并限制内存使用。
    - `TempCleaner`: 清理历史缓存。
    - `SessionWatcher`: 会话状态守卫。
- 全部采用 `asyncio.sleep` 循环，不再使用 `time.sleep`。
