# Web 故障与性能分析 (Web 500 & Lag Analysis)

## 背景 (Context)
用户反馈 Web 端大部分页面点击后出现 500 Internal Server Error，且系统运行极其缓慢卡顿。

## 策略 (Strategy)
1. **故障诊断**: 寻找 500 错误的 Traceback，定位崩溃点。
2. **性能审计**: 检查数据库锁、长任务阻塞或前端渲染瓶颈。
3. **修复与验证**: 修复代码 Bug，优化性能损耗点。

## 待办清单 (Checklist)

### Phase 1: 故障诊断 (Fault Diagnosis)
- [x] 检查 `logs/` 下的所有日志文件，寻找 500 相关的 Traceback。 (Result: No direct 500 trace found in logs)
- [x] 检查 `error_logs` 数据库表，查看是否有最近的异常记录。 (Result: Empty)
- [x] 验证 Web 服务运行状态 (Port, Process)。 (Status: Running but blocked)
- [ ] 模拟请求，获取 Trace ID 并关联日志。

### Phase 2: 性能分析 (Performance Analysis)
- [x] 检查主进程 CPU/内存 占用。 (Status: Normal, but Event Loop blocked)
- [x] 审计数据库查询耗时 (Slow Query)。 (Found: Synchronous DB connection in async route)
- [x] 检查是否存在死锁或长事务阻塞。 (Found: `psutil` blocking main thread)
- [x] 分析前端资源加载与渲染是否卡顿（CDN, JS 冲突等）。 (Found: High frequency DOM updates & CSS filters)

### Phase 3: 修复与优化 (Fix & Optimize)
- [x] 修复导致 500 的核心逻辑 Bug (Blocking Event Loop).
  - Fixed `web_admin/routers/stats_router.py`: Removed blocking `psutil` call and sync DB check.
- [x] 优化导致卡顿的瓶颈（如：异步化同步调用，增加索引，移除重型特效）。
  - Optimized `dashboard.html`: Added polling delay, reduced frequency, removed animation.
  - Optimized `base.html`: Disabled heavy CSS filters.

### Phase 4: 验收与报告 (Report)
- [ ] 任务总结报告 `report.md`。
- [ ] 更新 `process.md`。
