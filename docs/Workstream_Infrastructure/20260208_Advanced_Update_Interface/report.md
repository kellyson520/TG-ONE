# 任务报告: 增强升级与回滚全接口支持

## 1. 任务背景
在实现了“工业级更新守护逻辑”后，需要提供更易用的交互接口，支持通过 Python CLI 和 Telegram Bot 进行精确的版本更新（补丁升级）或强制回滚。

## 2. 核心改进 (Improvements)

### 2.1 统一管理接口 (Maximum Reuse)
- **封装**: 在 `UpdateService` 中封装了 `trigger_update(target)` 和 `request_rollback()`。
- **复用**: 无论是命令行工具、Bot 确认按钮，还是 Web 后台（未来扩展），都调用同一套逻辑。这避免了在不同入口重复编写写锁、停服和信号发送代码。

### 2.2 Python CLI 管理工具
- **路径**: `scripts/ops/manage_update.py`
- **功能**:
    - `status`: 检查当前版本及远程更新状态。
    - `upgrade [target]`: 升级到指定分支或 Commit。
    - `rollback`: 触发紧急回滚。
- **优势**: 支持在 SSH 终端通过 py 指令直接救急，无需打开 Telegram。

### 2.3 Bot 端交互增强
- **路径**: `handlers/commands/system_commands.py`
- **功能**:
    - `/update [target]`: 支持指定补丁版本，发送带二次确认的回调按钮。
    - `/rollback`: 紧急回滚入口，增加高风险操作警告。
    - `/history`: 查看最近 5 个版本，点击可直接跳转到指定版本的更新。
- **安全**: 严格限制 `is_admin` 权限。

### 2.4 补丁升级 (Patching) 能力
- 所有的更新指令现在都支持指定 `target`（可以是 `origin/main`，也可以是特定的 `SHA`）。
- 该 `target` 会被透传给守护进程 `entrypoint.sh`，通过 `git reset --hard` 实现精确版本定位。

## 3. 架构优势
通过这种方式，我们实现了：
1. **控制流解耦**: Python 只负责“下指令”（写锁并退出），Supervisor 负责“干脏活”（拉代码、装依赖、物理恢复）。
2. **多入口一致性**: 无论从哪个入口触发，最终执行逻辑完全一致，极大地降低了维护成本。

---
**Status**: ✅ Completed
**Version**: 3.2 (Full-stack Update Control)
