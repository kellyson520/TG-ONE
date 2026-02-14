# Report: Fix Unmatched Button Actions

## Summary
修复了 Admin Hub (系统管理中心) 中多个按钮点击后提示 `[UNMATCHED] Action` 的错误。通过在 `SystemMenuStrategy` 中补全缺失的动作定义，并完善其分发逻辑，确保了管理功能的连通性。

## Architecture Refactor
- **Handlers**: 更新了 `handlers/button/strategies/system.py` 中的 `SystemMenuStrategy` 类。
    - 扩充了 `ACTIONS` 集合，包含了 `AdminRenderer` 中定义的所有 `new_menu:` 前缀动作。
    - 在 `handle` 方法中增加了对新动作的支持，将其正确路由到 `MenuController`。

## Verification
- **Code Audit**: 
    - 经审计，`AdminRenderer` 中所有 22 个 `new_menu:` 动作均已在 `SystemMenuStrategy` 或相关策略类中有对应条目。
    - `system_logs` 现在正确映射到 `menu_controller.show_system_logs`。
    - `db_archive_center` 暂时映射到 `menu_controller.show_db_optimization_center` 以防止死链接。
    - `db_optimization_center`, `db_performance_monitor` 等动作已补全。
- **Static Analysis**: 检查了 Python 语法正确性。

## Manual
无需手动操作。系统启动后将自动应用新的策略路由。
若需验证，可进入“系统中心”点击“系统日志”或“数据库维护”等按钮，应不再出现 [UNMATCHED] 警告且页面能正常跳转。
