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
2.  **Testing**: 单元测试与集成测试 (pytest)。
3.  **Environment**: Python 3.10 on Ubuntu Latest (xvfb enabled).
