# Edge 浏览器卡顿问题修复

## 背景 (Context)

通过全面代码审查，锁定了导致 Edge 浏览器严重卡顿的"四大元凶"：
1. **后端死锁**: `psutil.cpu_percent(interval=0.1)` 阻塞异步事件循环
2. **WebSocket 与轮询冲突**: 断开瞬间高频 HTTP 请求加重服务器负担
3. **CSS 渲染过载**: 毛玻璃效果和动画导致合成器线程过载
4. **同步 I/O 阻塞**: `get_heartbeat()` 等同步调用阻塞事件循环

## 策略 (Strategy)

采用分层修复策略：
- **P0 (核心)**: 消除后端阻塞调用
- **P1 (逻辑)**: 优化前端轮询策略
- **P2 (渲染)**: 禁用高性能消耗 CSS 特效
- **P3 (隐患)**: 将同步 I/O 移入线程池

## 待办清单 (Checklist)

### Phase 1: 核心修复 (P0)
- [x] 修复 `stats_router.py` 中的 `psutil.cpu_percent` 阻塞调用
  - 将 `interval=0.1` 改为 `interval=None`
  - 添加详细注释说明非阻塞模式

### Phase 2: 异步安全 (P1)
- [x] 将 `get_heartbeat()` 移入线程池
  - 使用 `run_in_threadpool` 包装同步调用
  - 防止网络请求超时阻塞事件循环

### Phase 3: 前端优化 (已完成)
- [x] 验证 `dashboard.html` 轮询延迟策略
  - 确认 5 秒冷静期已实现
  - 确认轮询间隔已优化 (60s/10s/15s)
- [x] 验证 `base.html` CSS 优化
  - 确认 `.log-entry.animate-fade-in` 动画已禁用

### Phase 4: 验证与测试
- [x] 运行自动化验证脚本
  - ✅ psutil 非阻塞模式测试通过 (0.07ms < 10ms)
  - ✅ 代码修改验证通过
- [ ] 重启 Web 服务器
- [ ] 在 Edge 浏览器中测试仪表板页面
- [ ] 验证 CPU 占用率正常
- [ ] 验证滚轮操作流畅
- [ ] 验证 WebSocket 连接稳定

### Phase 5: 文档更新
- [x] 创建 `todo.md` 任务清单
- [x] 创建 `spec.md` 技术规格
- [x] 创建 `report.md` 修复报告
- [x] 创建验证脚本 `tests/verify_edge_fix.py`
- [ ] 更新 `process.md` 标记任务完成
