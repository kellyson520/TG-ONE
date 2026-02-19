# Worker 内存危机修复 (Worker Memory Crisis Fix)

## 背景 (Context)
系统在高负载运行时频繁触发 `[ResourceGuard] 内存危机会话`。
日志显示：`RSS=360.9MB > 150MB`。
当前问题：
1. `MEMORY_CRITICAL_THRESHOLD_MB` (150MB) 预设值过低，且与 `MEMORY_WARNING_THRESHOLD_MB` (250MB) 逻辑倒置。
2. 熔断逻辑过于频繁，每 10 秒触发一次 ERROR 日志并重启分发器，导致 Telegram 告警轰炸。

## 待办清单 (Checklist)

### Phase 1: 配置修正 (Configuration Correction)
- [x] 修正 `core/config/__init__.py` 中的内存阈值默认值。
- [x] 将阈值调整为更合理的范围（Warning: 512MB, Critical: 1024MB）。
- [x] 在 `.env` 中提供显式配置项以便用户调整。

### Phase 2: 熔断机制优化 (Circuit Breaker Optimization)
- [x] 优化 `WorkerService._monitor_scaling` 中的熔断逻辑，增加触发间隔或状态锁定。
- [x] 降低重复触发时的日志级别，或合并告警。
- [x] 确保 `gc.collect()` 在熔断期间更彻底地执行（使用 `gc.collect(2)`）。

### Phase 3: 内存占用分析 (Memory Analysis - Optional)
- [ ] 检查 Telethon 客户端是否保持了过大的消息缓存。
- [ ] 检查 Dispatcher 是否积压了过大的任务对象。

### Phase 4: 验证与验收 (Verification)
- [ ] 检查启动后的阈值加载是否正确。
- [ ] 验证在高内存占用（模拟）下熔断是否平滑且不轰炸。
