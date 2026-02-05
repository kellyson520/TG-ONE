# TG ONE 联网更新功能交付报告 (Report)

## 1. 任务概述 (Summary)
成功为 TG ONE 系统添加了可靠的联网更新功能。该功能支持定时自动检查、手动触发更新、本体代码同步（基于 Git）以及自动重启。

## 2. 核心产出 (Deliverables)

### 2.1 新增组件
- **`services/update_service.py`**: 更新服务中心，处理远程版本检测 (`git fetch`)、版本对比 (`rev-parse`) 和执行更新 (`git pull`)。
- **`/update` 命令**: 允许管理员手动触发更新检查与执行。

### 2.2 架构增强
- **`core/config/__init__.py`**: 扩展了 `Settings` 模型，支持 `AUTO_UPDATE_ENABLED`, `UPDATE_CHECK_INTERVAL`, `UPDATE_REMOTE_URL` 等配置。
- **`services/system_service.py`**: 增强了物理重启逻辑。通过 `os.execl` 实现物理进程替换，确保在 Windows/Unix 环境下即使没有外部进程管理器也能实现真正的重启。
- **`core/bootstrap.py`**: 将更新服务集成进系统引导序列，实现后台静默监控。
- **`handlers/commands/system_commands.py`**: 在系统状态指令中集成了版本更新预警。

## 3. 关键配置
用户可在 `.env` 中通过以下字段控制：
```env
AUTO_UPDATE_ENABLED=false     # 是否开启后台自动检查
UPDATE_CHECK_INTERVAL=86400    # 检查频率 (默认 24 小时)
UPDATE_REMOTE_URL=...         # 远程仓库地址
UPDATE_BRANCH=main            # 更新分支
```

## 4. 验证结果 (Verification)
- ✅ 配置文件解析验证：通过。
- ✅ 物理重启逻辑 (os.execl)：已按照可靠性标准重构，支持优雅关闭后物理替换进程。
- ✅ 命令集成：`/status` 现在会动态显示是否有新 Commit，`/update` 可执行全流程。
- ✅ 定时任务：已挂载至 `Bootstrap` 异步任务组。

## 5. 操作指南 (User Manual)
1. **检查更新**: 使用 `/status` 即可在版本信息下方看到新版本提示。
2. **立即更新**: 使用 `/update`，系统会拉取代码并自动重启。
3. **自动化**: 将 `AUTO_UPDATE_ENABLED` 设为 `true` 后，系统会自动跟进仓库最新代码。

---
任务已全链路对齐，文档已归档。
