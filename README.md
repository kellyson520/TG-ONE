# TG ONE Refactoring Project

[![TG ONE CI](https://github.com/kellyson520/TG-ONE/actions/workflows/ci.yml/badge.svg)](https://github.com/kellyson520/TG-ONE/actions/workflows/ci.yml)

Telegram 转发器核心重构项目 (Core Refactoring).

## 🚀 项目状态 (Project Status)
- **Version**: 1.2.2.4
- **Architecture**: Domain-Driven Design (DDD) + Service Layer
- **Progress**: Phase 6 (Web Admin Refactor)

## 🛠️CI/CD (持续集成)
本项目使用 GitHub Actions 进行自动化测试与构建。

### 触发机制
- **Push**: 推送代码到 `main` 分支时自动触发。
- **PR**: 提交 Pull Request 到 `main` 分支时自动触发。

### 检测内容
1.  **Linting**: 代码风格检查 (flake8)。
2.  **Testing**: 单元测试 with coverage gate.
3.  **Security**: 依赖漏洞扫描.

## 🔧 系统运维与升级 (Maintenance)

本项目内置了工业级的自动升级与回滚系统，支持以下三种管理方式：

### 1. 命令行管理 (CLI)
在服务器终端执行：
```bash
# 查看当前版本状态
python manage_update.py status

# 升级到指定分支或补丁版本 (Commit SHA)
python manage_update.py upgrade origin/main

# 紧急手动回滚
python manage_update.py rollback
```

### 2. Bot 指令管理
管理员可通过私聊机器人下达指令（带二次确认按钮）：
- `/update [target]` - 检查并执行系统升级/补丁同步。
- `/rollback` - 紧急回滚至上个稳定版本（含物理备份恢复）。
- `/history` - 查看最近 5 次版本更新记录。

### 3. 自动故障自愈 (Uptime Guard)
系统守护进程会自动监控更新后的运行状态。若更新后 **15 秒内** 发生持续崩溃（如语法错误、导入错误），将触发以下流程：
1. **自动识别**: 守护进程捕获更新后的不稳定状态。
2. **强制回滚**: 优先尝试 Git Reset 回滚，失败则自动从 `.tar.gz` 备份包还原核心文件。
3. **环境隔离**: 更新期间 Web 端自动进入 503 维护模式。
