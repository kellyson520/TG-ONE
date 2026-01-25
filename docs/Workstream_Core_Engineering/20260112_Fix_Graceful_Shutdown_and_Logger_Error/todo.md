# 任务清单

## 待处理
- [ ] 增加 `GuardService.stop_guards()` 方法 (services/system_service.py)
- [x] 优化 `main.py` 背景任务管理与优雅关停流程
- [x] 在 `utils/core/log_config.py` 增强日志初始化健壮性
- [ ] 验证修复结果 (运行模拟关闭测试)

## 状态
- 2026-01-12: 发现日志中存在 "A logger name must be a string" 异常及 Task 重启未清理问题，启动修复。
