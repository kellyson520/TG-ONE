# 任务清单: 修复更新流中断与系统挂件 (Todo List)

## 状态总览
- [x] 问题诊断: 确认异步任务残留导致的挂起 🚀
- [x] 核心修复-1: 补齐 `UpdateService` 的任务清理逻辑 (Task Lists)
- [x] 核心修复-2: 补齐 `SleepManager` 停止钩子
- [x] 核心修复-3: `main.py` 增加 40s 硬退出 fallback
- [x] 核心修复-4: 增强 Alembic 迁移的错误捕获能力
- [ ] 系统验证: 观察下一次更新请求的闭环情况

## 详细步骤

### Phase 1: 故障诊断 (Done)
- [x] 分析日志 `telegram-forwarder-opt-20260210120106.log`
- [x] 确认 `LifecycleManager: System shutdown complete.` 之后进程未消失

### Phase 2: 实施深度修复 (Done)
- [x] 更新 `services/update_service.py` 的任务管理与 Alembic 逻辑
- [x] 更新 `core/helpers/sleep_manager.py` 的 `stop` 逻辑
- [x] 更新 `core/bootstrap.py` 注册所有清理钩子
- [x] 更新 `main.py` 实施硬超时强制退出

### Phase 3: 归档与汇报 (Pending)
- [ ] 更新 `report.md` 中的最终故障成因分析
- [ ] 提交代码并推送
