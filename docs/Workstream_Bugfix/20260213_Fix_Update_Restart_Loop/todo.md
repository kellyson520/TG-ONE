# 任务: 修复更新重启循环与误触发回滚 (Fix Update Restart Loop)

## 背景 (Context)
系统在更新后处于观察期 (`restarting` 状态) 时，由于 `verify_update_health` 被重复调用 (一次在 `main.py` 启动时，一次在 `UpdateService` 启动时)，导致 `fail_count` 异常倍增。配合文件监听器触发的热重启，导致计数器迅速达到阈值 (3)，从而误触发紧急回滚。

## 待办清单 (Checklist)

### Phase 1: 核心逻辑修复
- [x] 移除 `services/update_service.py` 中 `start_periodic_check` 对 `verify_update_health` 的冗余调用。
- [x] 优化 `verify_update_health` 逻辑，增加进程级锁或防抖，确保单次启动流程中仅执行一次自检。
- [x] 优化 `fail_count` 增加逻辑，区分“崩溃导致重启”和“系统主动重启”。

### Phase 2: 安全与热重启防护
- [x] 在系统稳定性观察期 (Stabilization Period) 内，暂时抑制 `GuardService` 的 `Hot-Restart` 功能。
- [x] 确保 `.env` 文件的状态更新不会导致自循环重启。 (已通过上述抑制逻辑间接实现)

### Phase 3: 验证与验收
- [ ] 模拟更新后观察期启动，验证 `fail_count` 增长是否正常。
- [ ] 手动触发 `.env` 变化，验证在观察期内是否会导致误回滚。
- [ ] 编写测试用例覆盖此逻辑。
