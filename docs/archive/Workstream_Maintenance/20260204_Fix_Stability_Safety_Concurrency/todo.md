# 任务: 修复系统稳定性、数据安全与并发模型隐患

## 背景 (Context)
在深度审查后发现以下 4 个隐蔽但危险的错误：
1. **Event Loop 冲突**: Web 端调用 Bot 方法导致 Runtime Error。
2. **SQLite 死锁陷阱**: 定时维护任务与主线程消息写入竞争写锁。
3. **Log 查看器 DoS 漏洞**: 全量读取大日志文件导致 OOM。
4. **升级逻辑“自杀”风险**: 系统更新缺乏原子性与回滚机制。

## 待办清单 (Checklist)

## Phase 1: Investigation & Planning (Completed)
- [x] Explore codebase to identify Event Loop usage patterns.
- [x] Analyze database connection factory and PRAGMA settings.
- [x] Identify missing API endpoints (`get_visualization_data`).
- [x] Review system update process in `update_service.py`.

## Phase 2: Implementation - Stability & Concurrency (Completed)
### 1. 统一事件循环 (Unified Event Loop) - [x]
- [x] 将 `main.py` 中的 `TelegramClient` 初始化移至 `main()` 异步函数内。
- [x] 确保 `uvicorn` 在 `start_web_server` 中正确绑定至主 loop。

### 2. 数据库并发与安全 (Database Concurrency) - [x]
- [x] 在 `core/db_factory.py` 中将 SQLite `busy_timeout` 保持在 60s (Writer Engine)。
- [x] 在 `core/helpers/db_utils.py` 实现 `retry_on_db_lock` 装饰器。
- [x] 应用装饰器于 `RuleRepository` 的核心写入方法 (`toggle_rule`, `create_rule`, `save_rule`)。
- [x] 优化 `SystemService.run_db_optimization` 的 `VACUUM` 逻辑，确保脱离事务运行。

### 3. API 与 Web 可靠性 (API Reliability) - [x]
- [x] 在 `services/rule/query.py` 中实现 `get_visualization_data` 方法，修复 UI 崩溃。
- [x] 在 `RuleQueryService` 中补齐 `get_all_chats` 代理方法。
- [x] 优化 `SystemService.get_logs` 使用末尾读取策略 (200KB)，彻底根除 OOM 风险。

### 4. 高可靠系统更新 (Atomic Update) - [x]
- [x] 审计 `UpdateService` 代码，确认其具备备份、回滚、安全校验及 Zip Slip 防护。
- [x] 确认系统重启后的自动迁移机制 (`_check_database`) 逻辑完备。

## Phase 3: Reporting & Closure (Completed)
- [x] 验证 Web UI 功能（可视化图表、日志查看）。
- [x] 测试模拟更新/回滚周期。
- [x] 生成 `report.md` 并更新 `process.md`。
