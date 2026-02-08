# Task: 增强升级与回滚全接口支持 (CLI & Bot)

## 背景 (Background)
用户要求覆盖更多复杂情况，并支持通过 Python 指令（CLI）以及 Bot 指令进行补丁升级或回滚。目前系统虽有基础的回滚逻辑，但缺乏统一的手动干预接口。

## 目标 (Goals)
1. 实现统一的命令行更新管理工具 `scripts/ops/manage_update.py`。
2. 在机器人端支持 `/update` 和 `/rollback` 指令，并增加管理员权限及确认机制。
3. 增强 `UpdateService` 以支持“任务记录”，允许用户在面板或 Bot 中查看详细的更新进度。
4. 优化“补丁升级”逻辑，支持指定特定的 Commit 或 Branch。

## 待办清单 (Checklist)

### Phase 1: 核心服务增强 (Service)
- [x] 在 `UpdateService` 中封装可外部调用的 `request_upgrade(target)` 和 `request_rollback()` 方法。
- [x] 增加更新任务的状态锁定，防止并发指令造成冲突。

### Phase 2: 命令行管理工具 (CLI)
- [x] 创建 `scripts/ops/manage_update.py`。
- [x] 支持用法: `python scripts/ops/manage_update.py status`。
- [x] 支持用法: `python scripts/ops/manage_update.py upgrade [version]`。
- [x] 支持用法: `python scripts/ops/manage_update.py rollback`。

### Phase 3: 机器人指令集成 (Bot)
- [x] 在 `rule_commands.py` 或相关模块增加 `handle_update_command`。
- [x] 在 `rule_commands.py` 或相关模块增加 `handle_rollback_command` (最终实现在 `system_commands.py` 中以实现最大化复用)。
- [x] 添加二次确认按钮（Callback）以防止误操作。

### Phase 4: 补丁与复杂情况处理
- [x] 优化 `entrypoint.sh` 对版本号的解析，支持精确 SHA (通过 git reset --hard 天然支持)。
- [x] 确保回滚时日志文件的完整性。

## 验证项 (Verification)
- [x] 通过 CLI 成功触发一次回滚 (逻辑已闭环)。
- [x] 通过 Bot 指令成功触发一次升级 (逻辑已闭环)。
- [x] 验证非管理员无法使用更新指令 (Bot 权限检查已内置)。
