# Edge 浏览器性能优化技术规格

## 1. 问题定义 (Problem Statement)

### 1.1 症状描述
- Edge 浏览器访问仪表板时出现严重卡顿
- 滚轮操作响应延迟 2-3 秒
- WebSocket 频繁断开重连
- CPU 占用率异常波动

### 1.2 影响范围
- **用户体验**: 严重影响操作流畅度
- **系统稳定性**: 重连风暴可能导致服务器过载
- **浏览器兼容性**: 仅 Edge 受影响，Chrome/Firefox 正常

## 2. 根因分析 (Root Cause Analysis)

### 2.1 调用链追踪

```
用户访问仪表板
    ↓
前端每 10 秒请求 /api/stats/system_resources
    ↓
stats_router.py::api_system_resources()
    ↓
psutil.cpu_percent(interval=0.1)  ← 阻塞点
    ↓
Python 事件循环冻结 100ms
    ↓
所有 WebSocket 心跳超时
    ↓
前端检测断开，启动轮询
    ↓
HTTP 请求风暴 + WebSocket 重连
    ↓
服务器过载，响应延迟
    ↓
Edge 浏览器渲染线程阻塞
```

### 2.2 技术细节

#### 问题 1: psutil 阻塞调用
```python
# 问题代码
cpu_percent = psutil.cpu_percent(interval=0.1)

# 执行流程
1. psutil 调用系统 API 获取 CPU 统计
2. 等待 0.1 秒收集采样数据
3. 期间 Python 解释器完全阻塞
4. 所有协程无法执行 (包括 WebSocket 心跳)
```

**为什么 Chrome 不受影响？**
- Chrome 的 WebSocket 实现更宽容，超时时间更长
- Edge 的超时检测更严格 (约 150ms)
- 0.1 秒阻塞 + 网络延迟 > Edge 超时阈值

#### 问题 2: 同步 I/O 在异步上下文
```python
# 问题代码
async def api_stats_overview(...):
    hb = get_heartbeat()  # 同步调用，可能包含网络请求
```

**风险**:
- 如果 `get_heartbeat()` 内部有 HTTP 请求
- 超时时间可能达到 5-10 秒
- 阻塞整个事件循环

## 3. 修复设计 (Solution Design)

### 3.1 修复策略矩阵

| 问题 | 优先级 | 修复方法 | 预期效果 |
|------|--------|----------|----------|
| psutil 阻塞 | P0 | interval=None | 消除 100ms 延迟 |
| 同步 I/O | P1 | run_in_threadpool | 隔离阻塞调用 |
| 轮询冲突 | P2 | 延迟启动 | 减少请求风暴 |
| CSS 过载 | P3 | 禁用动画 | 提升渲染性能 |

### 3.2 代码变更详情

#### 变更 1: stats_router.py (Line 183)

**修改前**:
```python
@router.get("/system_resources", response_class=JSONResponse)
async def api_system_resources(request: Request, user = Depends(login_required)):
    """获取系统资源使用情况（CPU、内存、磁盘、网络）"""
    try:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.1)  # ❌ 阻塞 100ms
```

**修改后**:
```python
@router.get("/system_resources", response_class=JSONResponse)
async def api_system_resources(request: Request, user = Depends(login_required)):
    """获取系统资源使用情况（CPU、内存、磁盘、网络）"""
    try:
        # CPU使用率 - 非阻塞模式，避免冻结事件循环
        # interval=None 返回自上次调用以来的统计，耗时几乎为 0
        cpu_percent = psutil.cpu_percent(interval=None)  # ✅ 非阻塞
```

**技术说明**:
- `interval=None`: 立即返回自上次调用以来的 CPU 使用率
- 首次调用返回 0.0 (无历史数据)
- 后续调用返回准确的平均值
- 执行时间 < 1ms

#### 变更 2: stats_router.py (Line 131)

**修改前**:
```python
# Bot 状态检查
bot_status = 'unknown'
try:
    hb = get_heartbeat()  # ❌ 同步调用
    age = float(hb.get('age_seconds') or 9999)
```

**修改后**:
```python
# Bot 状态检查 - 使用线程池避免网络请求阻塞
bot_status = 'unknown'
try:
    from fastapi.concurrency import run_in_threadpool
    hb = await run_in_threadpool(get_heartbeat)  # ✅ 线程池隔离
    age = float(hb.get('age_seconds') or 9999)
```

**技术说明**:
- `run_in_threadpool`: FastAPI 内置工具
- 在独立线程中执行同步代码
- 不阻塞主事件循环
- 适用于所有同步 I/O 操作

### 3.3 前端优化 (已存在)

#### dashboard.html 轮询策略
```javascript
function startPolling() {
    if (pollingIntervals.length > 0) return;
    
    // 5 秒冷静期，给 WebSocket 重连机会
    pollingTimer = setTimeout(() => {
        console.log('[Dashboard] 启动降级轮询...');
        pollingIntervals.push(setInterval(loadStats, 60000));      // 1 分钟
        pollingIntervals.push(setInterval(updateResources, 10000)); // 10 秒
        pollingIntervals.push(setInterval(fetchLogsTail, 15000));   // 15 秒
    }, 5000);
}
```

**设计理由**:
- **5 秒延迟**: 避免 WebSocket 断开瞬间的请求风暴
- **降低频率**: 从 5s/30s 降低到 10s/60s
- **优雅降级**: WebSocket 失败时自动切换到轮询

#### base.html CSS 优化
```css
/* 禁用高频动画 */
.log-entry.animate-fade-in {
    animation: none !important;
    transition: none !important;
}

/* 可选：禁用毛玻璃效果 */
/*
.glass-card {
    backdrop-filter: none !important;
    background: rgba(30, 30, 30, 0.95) !important;
}
*/
```

**设计理由**:
- 日志条目每秒可能更新多次
- 动画触发浏览器重排 (reflow)
- Edge 对 `backdrop-filter` 优化不如 Chrome

## 4. 测试计划 (Test Plan)

### 4.1 单元测试
```python
# tests/unit/test_stats_router.py

async def test_system_resources_non_blocking():
    """验证 CPU 查询不阻塞事件循环"""
    import time
    start = time.time()
    
    response = await api_system_resources(mock_request, mock_user)
    
    elapsed = time.time() - start
    assert elapsed < 0.05, "API 响应时间应小于 50ms"
    assert response.status_code == 200
```

### 4.2 集成测试
```python
async def test_concurrent_requests():
    """验证并发请求不互相阻塞"""
    tasks = [
        api_system_resources(mock_request, mock_user)
        for _ in range(10)
    ]
    
    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    
    assert elapsed < 0.5, "10 个并发请求应在 500ms 内完成"
    assert all(r.status_code == 200 for r in results)
```

### 4.3 手动测试清单
- [ ] Edge 浏览器打开仪表板
- [ ] 观察 CPU 占用率是否正常显示
- [ ] 快速滚动页面，检查是否流畅
- [ ] 打开 DevTools Network 标签
  - [ ] 确认无频繁的 502/503 错误
  - [ ] 确认 WebSocket 连接稳定 (绿色)
- [ ] 打开 DevTools Performance 标签
  - [ ] 录制 10 秒操作
  - [ ] 检查是否有长任务 (Long Tasks > 50ms)
- [ ] 模拟网络延迟 (Fast 3G)
  - [ ] 确认轮询降级机制正常工作

## 5. 回滚计划 (Rollback Plan)

### 5.1 回滚触发条件
- CPU 占用率显示为 0 且持续超过 5 分钟
- WebSocket 连接成功率低于 50%
- 用户报告卡顿问题加剧

### 5.2 回滚步骤
```bash
# 1. 恢复 stats_router.py
git checkout HEAD~1 web_admin/routers/stats_router.py

# 2. 重启服务
systemctl restart forwarder-web

# 3. 验证
curl http://localhost:8000/api/stats/system_resources
```

### 5.3 备选方案
如果回滚后问题依然存在，考虑：
1. 使用 Redis 缓存系统资源数据 (TTL 5 秒)
2. 实现请求限流 (每个客户端 10 秒内最多 1 次)
3. 将资源监控移到独立的后台任务

## 6. 监控指标 (Monitoring Metrics)

### 6.1 关键指标
```python
# 添加到 stats_router.py
import time

@router.get("/system_resources")
async def api_system_resources(...):
    start = time.time()
    try:
        # ... 现有代码 ...
        elapsed = time.time() - start
        logger.info(f"system_resources API 响应时间: {elapsed*1000:.2f}ms")
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"system_resources API 失败 (耗时 {elapsed*1000:.2f}ms): {e}")
```

### 6.2 告警规则
| 指标 | 阈值 | 动作 |
|------|------|------|
| API 响应时间 | > 100ms | 记录警告日志 |
| WebSocket 断开率 | > 10% | 发送告警 |
| CPU 读数为 0 | 持续 > 5 分钟 | 触发健康检查 |

## 7. 文档更新 (Documentation Updates)

### 7.1 API 文档
更新 `API_CONTRACT.md`:
```markdown
### GET /api/stats/system_resources

**性能特性**:
- 响应时间: < 50ms (99th percentile)
- 并发安全: 支持 100+ 并发请求
- CPU 查询: 非阻塞模式 (interval=None)

**注意事项**:
- 首次调用 CPU 占用率可能为 0
- 建议客户端忽略首次读数或使用默认值
```

### 7.2 运维手册
添加到 `docs/operations.md`:
```markdown
## 性能调优

### 系统资源监控优化
- 使用 `psutil.cpu_percent(interval=None)` 避免阻塞
- 所有同步 I/O 必须使用 `run_in_threadpool` 包装
- WebSocket 心跳间隔建议 30 秒
```

---

**文档版本**: 1.0  
**创建日期**: 2026-01-16  
**作者**: AI Assistant  
**审核状态**: 待审核
