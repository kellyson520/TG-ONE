# 归档按钮修复任务清单

- [x] 诊断归档按钮缺失原因：确认是由于 `AdminRenderer` 重构时漏掉了该按钮。
- [x] 修复 `AdminRenderer.render_system_hub`：添加“归档中心”按钮。
- [x] 修复 `SystemMenu.show_system_settings`：添加“数据库归档”按钮以保持一致性。
- [x] 补齐 `AdminMenuStrategy` 中的动作处理逻辑 (`admin_vacuum_db`, `admin_analyze_db`, `admin_full_optimize`)。
- [x] 补齐 `MenuController` 中的 Missing Proxy 方法。
- [x] 验证按钮可见性与动作触发正常。
