# 技术方案: 转发统计显示修复 (Spec: Forward Stats Fix)

## 1. 问题诊断
1. **周期信息缺失**: `AdminController.show_forward_analytics` 调用的是 `get_detailed_stats`，该方法不返回 `period` 字典，导致 Renderer 显示 `?`。
2. **类型显示 Unknown**:
   - `AnalyticsService` 返回的字典键为 `name`，但 `MainMenuRenderer.render_forward_analytics` 预期键为 `type`。
   - `AnalyticsService` 中对 `message_type` 的默认处理可能存在回退导致 "Unknown"。
3. **数据不一致**: `get_detailed_stats` 返回的是 `daily_trends` 列表，而 Renderer 预期 `summary` 对象中的统计值。

## 2. 修改建议

### 2.1 AnalyticsService (services/analytics_service.py)
- 修改 `get_detailed_stats` 中的 `type_distribution` 生成逻辑，确保同时提供 `name` 和 `type` 键，或保持与 Renderer 统一。
- 优化 `message_type` 的解析，确保从数据库读取的类型能正确显示。

### 2.2 AdminController (controllers/domain/admin_controller.py)
- 将 `show_forward_analytics` 中的数据获取方法从 `get_detailed_stats` 变更为 `get_detailed_analytics`。
- `get_detailed_analytics` 已经封装了 `period` 和 `summary`，更适合详细统计页面。

### 2.3 MainMenuRenderer (ui/renderers/main_menu_renderer.py)
- 检查 `render_forward_analytics` 是否有健壮性保护，避免字段缺失导致崩溃。

## 3. 验证计划
- 检查代码修改后的逻辑流。
- 确认 `AdminController` 的调用参数正确。
