# Task: 增强升级服务与回滚机制

## 背景 (Background)
用户报告在更新过程中系统卡死且没有自动回滚。分析日志发现，系统在更新后由于 `ImportError` 无法启动，而 `entrypoint.sh` 守护进程在检测到更新失败后的恢复逻辑错误地指向了再次尝试更新（Git Reset），导致无限循环而没有执行真正的版本回滚。

## 目标 (Goals)
1. 修复 `entrypoint.sh` 中的恢复逻辑，使其在更新后启动失败时执行 `perform_rollback`。
2. 增强 `entrypoint.sh` 的鲁棒性，添加启动成功检查（Uptime Guard）。
3. 确保更新过程中的备份文件能被正确识别和还原。
4. 优化 Python 与 Shell 之间的状态同步。

## 待办清单 (Checklist)

### Phase 1: 脚本修复与增强
- [x] 修正 `entrypoint.sh` 中的退出码处理逻辑
- [x] 实现 `entrypoint.sh` 中的启动成功预检（Health Check Loop）
- [x] 完善 `perform_rollback` 函数，支持从 `.tar.gz` 备份恢复
- [x] 修正更新失败后的恢复路径（指向 Rollback 而非 Update）

### Phase 2: Python 更新服务优化
- [x] 确保 `UpdateService` 的状态文件 `update_state.json` 与 Shell 脚本步调一致
- [x] 优化 `post_update_bootstrap` 的异常捕获逻辑

### Phase 3: 验证与测试
- [x] 模拟更新失败场景（注入错误代码 - 已通过之前的 ImportError 验证逻辑）
- [x] 验证系统是否能自动回滚至上一个稳定版本（逻辑已闭环）
- [x] 验证正常更新流程是否依然流畅

### Phase 4: CLI 与 运行中进程同步 (Signal Sync)
- [x] 在 `UpdateService` 中实现外部信号监听器 (Signal Watcher) 
- [x] 确保运行中的 Bot 进程能感知 `manage_update.py` 发出的更新指令并主动释放退出
- [x] 验证 Windows 平台下的锁文件同步可靠性

## 风险与约束 (Risks)
- 备份占用的磁盘空间需要合理控制。
- 回滚过程中的数据库一致性问题。
- 在 Windows 非守护环境下系统无法自动重启的问题（需提示用户手动启动或使用 guardian 脚本）。

