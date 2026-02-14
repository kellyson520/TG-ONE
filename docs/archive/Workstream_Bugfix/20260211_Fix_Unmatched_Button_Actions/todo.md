# Fix Unmatched Button Actions

## 背景 (Context)
在系统管理界面（Admin Hub）中，多个按钮点击后触发了 `[UNMATCHED] Action` 错误。
具体涉及 `system_logs` 和 `db_archive_center` 等动作。
这些动作在 `AdminRenderer` 中定义，但在 `SystemMenuStrategy` 的 `ACTIONS` 集合中缺失，导致策略分发器（Registry）无法匹配。

## 待办清单 (Checklist)

### Phase 1: 审计与分析
- [x] 扫描 `admin_renderer.py` 中的所有 `new_menu:` 动作
- [x] 审计 `SystemMenuStrategy.ACTIONS` 缺失项：
    - `system_logs` (替代 `log_viewer`)
    - `db_optimization_center`
    - `db_performance_monitor`
    - `refresh_db_performance`
    - `db_query_analysis`
    - `db_performance_trends`
    - `db_alert_management`
    - `run_db_optimization_check`
    - `db_reindex`
    - `db_archive_center`
    - `db_optimization_config`
    - `clear_dedup_cache`
- [x] 审计 `MenuController` 相关方法的实现状态

### Phase 2: 修复与实现
- [x] 更新 `SystemMenuStrategy.ACTIONS`
- [x] 更新 `SystemMenuStrategy.handle` 分发逻辑
- [x] 确保 `MenuController` 拥有对应的业务逻辑方法

### Phase 3: 验证
- [x] 运行静态检查
- [x] 逻辑审计通过
- [x] 更新 `report.md`

## 备注
- `system_logs` 应对应原有 `log_viewer` 的功能
- `db_archive_center` 应对应数据库归档管理
