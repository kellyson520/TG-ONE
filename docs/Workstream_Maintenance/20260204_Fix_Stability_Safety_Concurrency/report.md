# 任务报告: 系统稳定性、并发模型与数据安全修复 (2026/02/04)

## 1. 任务概述
本次任务针对系统在并发环境下出现的 Event Loop 冲突、数据库锁死、大日志文件导致的 OOM 风险以及系统更新非原子化问题进行了全面修复和加固。

## 2. 核心变更说明

### 2.1 统一事件循环 (Event Loop Stability)
- **问题**: 在 `main.py` 中模块级初始化 `TelegramClient` 会导致客户端绑定在错误的循环上，当 Web 端异步调用 Bot 方法时常触发 `RuntimeError`。
- **修复**: 将客户端初始化完全移入 `main()` 异步主函数，确保所有组件共享 `asyncio.run()` 创建的同一个运行循环。

### 2.2 数据库并发加固 (SQLite Concurrency)
- **问题**: SQLite 在并发写入（如维护任务与消息处理）时易触发 `database is locked`。
- **修复**: 
    - 引入 `retry_on_db_lock` 装饰器（位于 `core/helpers/db_utils.py`），采用指数退避算法（Exponential Backoff with Jitter）自动重试被锁定的写入操作。
    - 应用于 `RuleRepository` 的核心方法 (`create_rule`, `save_rule`, `toggle_rule`)。
    - 确保 `VACUUM` 操作在独立的非事务连接中运行，避免事务嵌套冲突。

### 2.3 日志查看器 DoS 漏洞修复 (Memory Safety)
- **问题**: `SystemService.get_logs` 原本使用 `f.readlines()` 读取全量日志，在生产环境日志文件过大（GB 级）时会直接导致 OOM。
- **修复**: 改用 `seek` 定位到文件末尾，仅读取最后 200KB 数据进行行切分，确保无论日志文件多大，内存占用始终恒定在极低水平。

### 2.4 API 功能补齐 (UI Reliability)
- **问题**: 前端规则可视化页面调用 `get_visualization_data` 方法时因为后端未实现而导致 500 错误。
- **修复**: 在 `RuleQueryService` 中补齐了 `get_visualization_data` 和 `get_all_chats` 方法，实现了完整的节点-连线图谱数据构造逻辑。

### 2.5 系统更新安全性审计 (Atomic Update)
- **风险**: 担忧更新过程损坏代码或无法回滚。
- **审计结果**: `UpdateService` 已具备完善的备份还原机制、URL 安全校验、SHA 交叉验证以及 Zip Slip 漏洞防御，结构非常稳固。

## 3. 质量门禁验证
- [x] **Event Loop**: 经代码审计，确认客户端绑定逻辑已收敛至异步上下文。
- [x] **DB Locking**: 模拟并发写入下，重试逻辑工作正常，未见崩溃。
- [x] **Log OOM**: 实测读取 100MB+ 日志文件，瞬间返回且内存无波动。
- [x] **UI Visualization**: 规则可视化 API 返回正确的图谱 JSON。

## 4. 结论
系统整体健壮性得到显著提升，消除了多个可能导致生产环境宕机的隐患。建议后续保持对 SQLite 写入频率的监控。
