# 技术方案: 修复更新流中断与系统挂起 (Technical Spec)

## 问题分析
用户反馈系统收到 "processing" 信号后卡死且未进行更新。
经分析，存在以下核心缺陷：
1. **竞争条件与延迟**: `UpdateService` 的信号监听器在检测到信号后，存在一个 1 秒的 `asyncio.wait_for` 延迟。如果在系统关闭流程中检测到信号，系统主循环可能在延迟结束前就已返回 `exit_code=0` 并退出/挂起。
2. **EventBus 挂起风险**: 在 `container_shutdown` (Priority 2) 完成后，`UpdateService` (未注册优先级) 仍尝试通过 `EventBus` 发布事件。如果总线资源已释放，可能导致协程挂起。
3. **无限循环任务**: `Bootstrap.py` 中的 `_resource_monitor_loop` 和 `UpdateService` 的后台任务没有正确注册在关闭流程中，导致 `asyncio.run` 在清理阶段可能因为无法结束这些任务而挂起。
4. **代码逻辑错误**: `Bootstrap.py` 中 `while not self.coordinator.is_shutting_down` 将方法对象视为布尔值，导致循环永远不会因为关闭信号而停止。

## 修复方案
1. **消除更新延迟**:
   - 移除 `_watch_external_signals` 中的 1s 手动延迟。
   - 增加 `is_closing` 检查。若系统已在关闭中，跳过 `_emit_event` (EventBus) 直接更新 `exit_code`。
2. **完善关闭链路**:
   - 在 `Bootstrap._register_shutdown_hooks` 中显式注册 `update_service.stop()`。
   - 修正 `is_shutting_down` 方法调用。
3. **优先级重置**:
   - 确保 `UpdateService` 在检测到更新信号时，无论当前是否在关闭中，都强制将 `lifecycle.exit_code` 设置为 `10 (EXIT_CODE_UPDATE)`。

## 预期效果
- 当外部执行 `python manage_update.py upgrade` 时，主程序能立即响应并以退出码 10 结束。
- `entrypoint.sh` 接收到退出码 10，正确执行 `perform_update` (Git/Uv 同步)。
- 系统在退出阶段不再因为后台任务残留而卡死。
