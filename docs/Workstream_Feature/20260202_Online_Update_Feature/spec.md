# TG ONE 联网更新功能方案 (Spec)

## 1. 背景 (Context)
用户需要为 TG ONE 添加可靠的联网更新功能，支持：
- 自定义检查频率（定时任务）。
- 自动更新本体（代码同步）。
- 复用现有热重启模块（GuardService）实现无感/自动重启。

## 2. 核心逻辑与组件 (Architecture)

### 2.1 更新策略 (Update Strategy)
考虑到项目基于 Git 管理，最可靠的更新方式是 `git pull`。为了兼容非 Git 环境或更灵活的发布（虽然目前主要用 Git），我们将实现一套基于 `UpdateService` 的逻辑：
1. **获取远程版本**: 访问远程 `version.py` 或特定的 `version.json` / GitHub API。
2. **版本对比**: 将本地 `version.py` 的 `VERSION` 与远程版本进行语义化比较。
3. **执行更新**: 
   - 模式 A (Git): 执行 `git pull`。
   - 模式 B (Raw): 下载源码包并覆盖（可选，暂以 Git 优先，因为它是最可靠的）。
4. **依赖更新**: 执行 `pip install -r requirements.txt` (可选，依据是否有变化)。
5. **触发重启**: 调用 `guard_service.trigger_restart()`。

### 2.2 配置项 (Settings)
在 `core/config/__init__.py` 中添加：
- `AUTO_UPDATE_ENABLED`: 是否开启自动更新（默认 False）。
- `UPDATE_CHECK_INTERVAL`: 检查间隔（秒，默认 86400 即 24 小时）。
- `UPDATE_REMOTE_URL`: 远程版本信息 URL 或 GitHub Repo 路径。
- `UPDATE_BRANCH`: 更新分支（默认 "main"）。

### 2.3 `UpdateService` 设计
- **方法**:
  - `check_for_updates()`: 执行版本检查逻辑。
  - `perform_update()`: 执行实际的文件替换/git pull。
  - `start_update_task()`: 作为后台任务定期运行。
- **依赖**: 注入 `guard_service` 以便完成更新后重启。

## 3. 实现细节 (Implementation Steps)

### Phase 1: 配置扩展
- 修改 `Settings` 类，增加更新相关字段。
- 支持从 `.env` 加载这些配置。

### Phase 2: UpdateService 实现
- 创建 `services/update_service.py`。
- 实现 `check_for_update` (使用 `httpx` 或 `requests` 获取版本)。
- 实现 `apply_update` (执行命令 `git pull`)。
- 实现 `loop_task` (异步循环)。

### Phase 3: 集成与触发
- 在 `Bootstrap._start_auxiliary_services` 中启动 `UpdateService`。
- 在 `handlers/commands/system_commands.py` 添加 `/update` 手动触发命令。

### Phase 4: 重启增强
- 修改 `guard_service._restart_process_async`，如果是在 Windows 且非 Docker 环境，使用 `os.execl` 确保物理重启。

## 4. 可靠性保证 (Reliability)
- **原子性**: 采用 `git reset --hard` 策略，确保代码状态与远程绝对同步，解决冲突。
- **健康检查 (Health Check)**: 启动后监控 60s。若启动后短时间内崩溃，系统会检测到。
- **连续失败检测 (Boot Loop Protection)**: 若连续 3 次启动失败，自动触发 `rollback` 回滚至上一个已知稳定版本。
- **紧急回滚 (Rollback)**: 支持 `/rollback` 命令手动一键还原。
- **网络预检 (Network Pre-check)**: 更新前验证 GitHub 连接，避免半更新状态。
- **重启可靠性**: 引入 `time.sleep(0.5)` 延迟 re-exec，确保 Windows 锁释放。

## 5. 待确认
- 是否需要支持非 Git 环境？暂定强制要求 Git 环境以保证可靠性。
