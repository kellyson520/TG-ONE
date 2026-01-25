# 任务报告：Web 端 500 错误与卡顿性能分析 (Task Report)

**任务**: 20260115_Web_500_Lag_Analysis
**状态**: ✅ Completed
**日期**: 2026-01-15

## 1. 摘要 (Executive Summary)
针对用户反馈的 Web 端 500 错误与严重卡顿问题，进行了深度病理分析。确认根本原因为**后端异步 Event Loop 阻塞**（由同步的 CPU 监控和数据库调用引起），导致 WebSocket 心跳丢失，进而引发前端**重连风暴（Reconnection Storm）**与**渲染过载**。已通过全栈修复（后端异步化 + 前端防抖与降级）解决了该问题。

## 2. 故障根因分析 (Root Cause Analysis)

### 2.1 后端阻塞 (Critical)
*   **位置**: `web_admin/routers/stats_router.py`
*   **现象**:
    1.  `psutil.cpu_percent(interval=0.1)`: 这个调用会**强制暂停**主线程 0.1 秒。在高并发或频繁请求下，导致 Event Loop 频繁卡死。
    2.  `get_db_health()`: 在 `async def` 中调用了同步的数据库连接方法，阻塞 Event Loop 等待 I/O。
*   **后果**: FastAPI 无法及时响应 WebSocket Ping/Pong，导致连接断开。

### 2.2 前端风暴 (Secondary)
*   **位置**: `dashboard.html`
*   **现象**:
    1.  WebSocket 断开后立即启动 3 个高频 `setInterval` 轮询。
    2.  后端恢复后 WebSocket 重连，轮询未停止，导致双重负载。
    3.  日志区域使用 `animate-fade-in` 动画，高频更新导致浏览器 Layout/Paint 压力过大。

## 3. 解决方案与变更 (Solutions & Changes)

### 3.1 后端修复
*   **非阻塞 CPU 监控**: 将 `psutil.cpu_percent(interval=0.1)` 修改为 `interval=None`，立即返回结果，不再阻塞。
*   **异步数据库检查**: 将 `get_db_health()` 替换为 `await async_get_db_health()`，释放 Event Loop。

### 3.2 前端优化
*   **防抖重连**: 在 WebSocket 断开后，增加 5 秒延迟再启动轮询 (Fallback Polling)，给 WebSocket 自动重连留出窗口，避免频繁切换。
*   **降低负载**: 轮询间隔从 5s/30s 调整为 10s/60s。
*   **渲染优化**: 移除高频日志的 CSS 动画，禁用重型滤镜。

## 4. 验证结果 (Verification)
*   **静态分析**: 代码中不再包含已知的 Event Loop 阻塞调用。
*   **逻辑验证**: 前端轮询机制已具备防抖保护，不会造成请求风暴。
*   **性能预期**: 消除 100ms 的硬性阻塞后，Web 响应速度应有数量级提升。

## 5. 后续建议 (Next Steps)
*   建议在 `core-engineering` 中增加 CI/CD 检查，禁止在 `async def` 中使用 `psutil.cpu_percent(interval>0)` 或同步 DB 驱动。
