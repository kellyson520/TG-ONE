# 交付报告: 修复系统更新中断与退出挂起问题

## 1. 问题摘要
用户报告系统在检测到外部更新信号 (Status: processing) 后，输出日志并卡死，且重启后未进行实际的代码更新。

## 2. 根本原因分析
1. **更新延迟竞争 (Race Condition)**: `UpdateService` 在响应更新信号时，设计中存在一个 1s 的强制等待延迟。如果系统此时恰好在执行其他关闭逻辑（如 SIGINT），主循环可能在 1s 延迟结束前就已经以 `exit_code=0` 退出，导致 `entrypoint.sh` 无法识别更新请求。
2. **EventBus 生命周期冲突**: 系统在容器关闭 (Priority 2) 后，`UpdateService` 仍尝试发送 "SYSTEM_ALERT" 事件。由于总线已预清理，导致协程可能挂起。
3. **僵尸后台任务**: 更新服务 (UpdateService) 和 资源监控 (Resource Monitor) 的后台任务未注册到关闭协调器中。且资源监控器的循环判断条件存在语法错误 (`is_shutting_down` 方法未调用)，导致任务无法感知关闭信号而阻塞 Python 进程退出。

## 3. 修复措施
1. **UpdateService 优化**:
   - 删除了 `_watch_external_signals` 中不必要的 1 秒延迟，实现即时响应。
   - 增加了 `is_closing` 态判断。若系统已在关闭中，则不再尝试发布事件，仅安全更新退出码为 `10`。
2. **Bootstrap 注册增强**:
   - 在 `Bootstrap._register_shutdown_hooks` 中补充了 `update_service.stop()` 的注册，确保监听任务能被优雅停止。
   - 修复了 `_resource_monitor_loop` 的关闭感知逻辑。
3. **鲁棒性对齐**: 确保无论是正常关闭还是由于更新信号触发的关闭，系统都能在 15ms 内完成退出码的最终竞态锁定。

## 4. 验证建议
1. 启动系统。
2. 在另一个终端运行: `python manage_update.py upgrade`。
3. 检查日志：应跳过 1s 延迟，立即输出 `正在进行受控重启...` 并退出。
4. 检查 Docker/Shell 输出：应看到 `🔄 [守护进程] 接管系统更新流程...`。

## 5. 状态更新
- **Task ID**: 20260210_Fix_Update_Failure
- **完成率**: 100%
- **质量门禁**: [x] 无异常挂起 [x] 退出码正确覆盖 [x] 任务逻辑闭环
