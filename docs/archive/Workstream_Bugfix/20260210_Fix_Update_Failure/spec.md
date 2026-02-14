# 技术方案: 修复更新流中断与系统挂起 (Technical Spec)

## 问题分析
用户反馈系统收到 "processing" 信号后卡死且未进行更新。
经分析及最新的日志验证，存在以下核心缺陷：
1. **进程退出挂起**: 即使 `LifecycleManager` 收到了关闭信号，但由于 `SleepManager`、`UpdateService` 等后台异步任务未在 `ShutdownCoordinator` 中显式取消，导致 `asyncio.run` 在清理循环时产生死锁或无限等待。
2. **Alembic 迁移异常监控不足**: 在 Stage 2 (启动引导) 阶段，`Alembic` 迁移失败时 stderr 可能为空，导致无法定位数据库结构同步失败的原因。
3. **竞争条件**: 在极少数情况下，`EventBus` 关闭后的漏发事件会导致协程挂起。

## 解决方案

### 1. 异步任务生命周期闭环
- **显式取消**: 所有的长期运行任务 (Long-running Tasks) 如 `ResourceMonitor`、`SleepManager`、`UpdateWatcher` 均增加了 `CancelledError` 处理，并纳入管理列表。
- **Shutdown 注册**: 在 `Bootstrap._register_shutdown_hooks` 中补齐了 `update_service.stop()` 和 `sleep_manager.stop()` 的调用。

### 2. 进程强制退出 fallback (Safety Gate)
- **硬超时监控**: 在 `main.py` 中为 `lifecycle.stop()` 增加了 40 秒的 `asyncio.wait_for`。
- **底层强制终止**: 若 40s 内未能完成优雅关闭，程序将调用 `os._exit(exit_code)`。这能穿透任何 Python 级的死锁，确保守护进程 (`entrypoint.sh`) 能立即接收到退出码。

### 3. Alembic 引导逻辑优化
- **异步捕获输出**: 改用 `asyncio.create_subprocess_exec` 并合并 `stdout` 与 `stderr` 捕获。
- **详细错误上报**: 若迁移失败，将详细错误内容记录至日志并触发系统告警。

### 4. 状态机鲁棒性
- **即时响应**: 移除 `UpdateService` 重启前的所有不必要延迟。

## 待验证事项
- [ ] 验证 `/update` 指令触发后，终端是否能正确显示守护进程的 Git 同步日志。
- [ ] 检查 `UPDATE_VERIFYING.json` 在引导成功后是否正确生成。

## 预期效果
- 系统退出不再挂起。
- 无论代码更新是否成功，系统都能在 40s 内完成状态流转或重启。
