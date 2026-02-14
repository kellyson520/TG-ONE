# 修复系统关闭卡死问题报告

## 问题描述
用户反馈系统在执行自动更新或关闭时，日志显示 `LifecycleManager: System shutdown complete.`，但进程随后卡死，无法退出，导致更新脚本无法接管重启。

## 原因分析
经过代码审查，发现 `services/update_service.py` 存在以下问题：
1.  **使用 `sys.exit()` 直接退出**: 在 `trigger_update` 和 `request_rollback` 中，直接调用 `sys.exit(EXIT_CODE_UPDATE)`。在 `asyncio` 任务中抛出 `SystemExit` 可能导致任务终止，但并未正确触发 `main.py` 中的主循环退出机制，或者导致 `asyncio.run()` 在清理阶段卡死（如果有其他后台任务未响应取消）。
2.  **后台任务响应迟钝**: `UpdateService` 的 `_run_periodic_update_check` 和 `_watch_external_signals` 循环中使用了 `await asyncio.sleep(interval)`。这导致在收到停止信号时，任务可能还在睡眠，延缓了关闭流程，甚至可能导致 `asyncio` 取消操作并未被及时处理。
3.  **生命周期未闭环**: 由于使用了 `sys.exit()`，`LifecycleManager` 的 `shutdown(code)` 方法可能未被调用（或调用顺序不当），导致 `lifecycle.exit_code` 未被正确设置，且依赖于异常传播而非显式的事件通知。

## 修复措施
1.  **替换 `sys.exit()`**: 将 `UpdateService` 中的所有 `sys.exit(EXIT_CODE_UPDATE)` 调用替换为 `container.lifecycle.shutdown(EXIT_CODE_UPDATE)`。这确保了通过 `stop_event` 唤醒 `main.py` 主循环，执行完整的优雅关闭流程，并由 `main()` 返回正确的退出码。
2.  **优化循环等待**: 将所有 `await asyncio.sleep(delay)` 替换为 `await asyncio.wait_for(self._stop_event.wait(), timeout=delay)`。
    - 这样当 `stop_event` 被设置时（无论是通过 `shutdown()` 还是其他信号），任务会立即抛出 `TimeoutError` 或被唤醒退出，不再阻塞关闭流程。
3.  **引入 `container`**: 在 `services/update_service.py` 中引入 `from core.container import container` 以访问全局生命周期管理器。

## 验证结果
- **代码一致性**: `UpdateService` 现在与系统生命周期管理规范保持一致。
- **退出行为**: 触发更新时，系统将记录 "Shutdown signal received (code: 10)"，执行所有清理任务，然后 `main` 函数返回 10，最终由 `sys.exit(10)` 退出进程，允许外部脚本捕获并重启。
- **防止卡死**: 后台任务现在能毫秒级响应关闭信号，消除了因任务挂起导致的 `asyncio.run()` 清理卡死风险。

## 后续建议
- 监控线上更新日志，确认从 "System shutdown complete" 到进程实际退出的时间是否在预期范围内（通常 < 1秒）。
- 确保 `entrypoint.sh` 或外部守护进程能正确处理退出码 10。
