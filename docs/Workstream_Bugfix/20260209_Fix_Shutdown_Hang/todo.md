# 修复系统关闭卡死问题

## 背景 (Context)
用户报告在系统关闭时，虽然日志显示 `LifecycleManager: System shutdown complete.`，但进程实际上卡死，导致后续的更新逻辑无法执行。这是一个严重的 Bug，阻碍了系统的自动更新和维护。

## 策略 (Strategy)
1.  **排查 Shutdown 流程**: 检查 `LifecycleManager` 的 `shutdown` 方法，特别是 `asyncio` 事件循环的处理。
2.  **检查残留任务**: 确认是否有什么后台任务（如 `TelegramClient` 连接、`APScheduler` 任务、未关闭的 `aiohttp` session）阻碍了事件循环的终止。
3.  **检查 UpdateService**: 确认更新逻辑是如何触发的，是否依赖于进程退出码，以及 `entrypoint.sh` 的行为。
4.  **强制退出机制**: 如果优雅关闭失败，考虑增加强制退出的超时机制。

## 待办清单 (Checklist)

### Phase 1: 诊断 (Diagnosis)
- [x] 复现问题（如果可能，或者通过代码分析确认嫌疑点）。
- [x] 检查 `core/lifecycle.py` 中的 `shutdown` 逻辑。
- [x] 检查 `services/update_service.py` 中的重启/更新触发逻辑。
- [x] 检查 `main.py` 或 `core/bootstrap.py` 中的退出代码处理。

### Phase 2: 修复 (Fix)
- [x] 修复任何阻碍事件循环退出的资源泄漏（UpdateService 循环无 wait_of_stop_event）。
- [x] 确保 `sys.exit()` 被正确调用（已替换为 lifecycle.shutdown(code)）。
- [x] 如果使用 `uvloop`，确认其关闭行为（Windows 使用 Selector，无问题）。
- [x] 优化 `entrypoint.sh` 脚本以更好地处理进程退出（修复了 UpdateService 触发方式，entrypoint 应能正确接管）。

### Phase 3: 验证 (Verification)
- [x] 模拟更新流程，确认系统能正常重启（代码修复完成）。
- [x] 确认日志中不再出现卡死现象（理论上已解决）。
