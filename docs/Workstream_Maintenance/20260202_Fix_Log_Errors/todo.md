# 修复日志报错 (Fix Log Errors)

## Context
根据日志 `telegram-forwarder-opt-20260202200428.log` 分析，系统存在严重的数据库损坏、模块缺失及前端模板错误。本任务旨在修复这些阻断性问题。

## Strategy
1.  **Frontend Fix**: 修复 `web_admin` 模板语法错误。
2.  **Bootstrap Fix**: 修复启动脚本中丢失的 `database_health_check` 模块引用。
3.  **Database Recovery**: 尝试修复或重置损坏的 SQLite 数据库文件。
4.  **Static Files**: 检查并修复 404 静态资源路径。

## Checklist

### Phase 1: Critical Fixes (阻断性修复)
- [x] 修复 `web_admin/templates/tasks.html` 中的 `TemplateSyntaxError` (未知标签 `endblock`)
- [x] 修复 `core/bootstrap.py` (预测位置) 中对 `scripts.database_health_check` 的导入错误
- [x] 验证 `database_health_check` 脚本是否存在，若不存在则创建或迁移逻辑

### Phase 2: Database Integrity (数据完整性)
- [x] 诊断 `/app/sessions/backup/user.before_repair_*.session` 及 `/app/db/forward.db` 的损坏情况
- [x] 提供或执行数据库修复方案 (如 `.dump` 重建)
- [x] 验证数据库连接恢复正常

### Phase 3: Frontend Polish (前端优化)
- [x] 修复静态资源 404 错误 (`bootstrap-icons.woff2`, `resources` API)
- [x] 验证 Web Admin 页面加载无报错

### Phase 4: Verification (验证)
- [x] 重启系统，确认无 Error 日志
- [x] 确认 Web Admin 正常访问
