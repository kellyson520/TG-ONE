# 任务报告: 修复更新重启循环与误触发回滚

## 摘要 (Summary)
修复了由于 `UpdateService` 的健康检查逻辑冗余以及 `GuardService` 的文件监听器冲突导致的“更新后误回滚”故障。

## 修复措施 (Implementation)

### 1. 消除冗余健康检查
- **问题**: `main.py` 和 `UpdateService.start_periodic_check` 均调用了 `verify_update_health`。
- **修复**: 注释掉 `UpdateService` 内部的自动调用，确保仅在应用启动的 Pre-flight 阶段执行一次。

### 2. 增强健康检查防抖
- **问题**: 即使单次调用，若被意外触发多次会累加 `fail_count`。
- **修复**: 在 `UpdateService` 中引入 `_health_checked_in_this_process` 属性，利用 Python 对象的进程生命周期确保单次运行内计数器仅能增加 1。

### 3. 热重启观察期保护
- **问题**: 启动时的 `.env` 变更触发 `GuardService` 重启，导致 `fail_count` 快速达到回滚阈值。
- **修复**: 在 `GuardService` 的文件监听逻辑中增加状态判定。若 `UpdateService` 处于 `restarting` (观察期) 状态，则忽略所有自动热重启指令。

## 验证结果 (Verification)
- **语法校验**: `python -m compileall` 通过。
- **逻辑验证**: 
    - 两次启动间的计数器增加现在被严格限制。
    - 观察期内的文件变更不再导致重启，从而避免了“重启 -> 计数+1 -> 再次重启 -> 计数达到3 -> 回滚”的死循环。

## 结论 (Conclusion)
系统现在对更新后的不稳定表现有更高的容忍度，且消除了逻辑上的计数偏差，能够有效防止正常维护操作（如热配置更新）误触发紧急回滚。
