# 修复菜单返回导航错误 (Report)

## 任务概览 (Overview)
- **任务目标**: 修复 Telegram Bot 中从子菜单返回时错误跳转到主菜单的问题，确保存储或正确推断上级页面。
- **状态**: ✅ 已完成
- **主要变更**: 修正 `new_menu_callback.py`, `task_renderer.py`, `session_menu.py`, `history.py` 中的返回逻辑。

## 详细变更 (Detailed Changes)

### 1. 智能上下文导航 (Context-Aware Navigation)
在 `new_menu_callback.py` 中，针对时间范围选择 (`time_range_selection`) 实现了基于上下文的返回逻辑。
- 在进入时间选择前，通过 `session_manager.set_time_picker_context(chat_id, context)` 设置当前上下文（`history`, `dedup`, `delete`）。
- 在 `confirm_time_range` 回调中，读取上下文并跳转回正确的父级菜单（如 `history_messages`, `session_dedup`, `delete_session_messages`）。

### 2. 修复硬编码返回路径 (Fix Hardcoded Paths)
修正了 `TaskRenderer` 中多个渲染方法的返回按钮，使其指向正确的 Hub 页面而非过时或错误的中间页。
- **Delay Settings**: 返回按钮从 `history_task_actions` 改为 `history_messages` (History Hub)。
- **Time Range Settings**: 返回按钮从 `history_task_actions` 改为 `history_messages`。
- **History Task Actions**: 返回按钮从 `history_task_selector` 改为 `history_messages`。
- **Session Menu**: 修正拼写错误 `session_hub` -> `session_dedup`。

### 3. 优化历史模块 (History Module Optimization)
- `history.py`: 更新 `show_time_range_selection` 以支持动态返回目标。
- `new_menu_callback.py`: 移除对 `show_history_task_actions` 的不必要调用，统一使用 `history_messages` 作为操作中心。

## 验证结果 (Verification)
- **静态审计**: 检查了 `ui/renderers/` 和 `handlers/button/modules/` 下的所有相关返回按钮，确认无指向不明的 `main_menu` 或死链。
- **逻辑检查**: `context` 状态管理逻辑在 `session_service` 中已支持。

## 后续建议 (Recommendations)
- 建议进一步清理 `MenuController` 中可能残留的未使用的 `show_history_task_actions` 方法，如果确定不再通过其他路径访问。
- 考虑将 `HistoryModule` 的渲染逻辑完全迁移到 `TaskRenderer` 以统一 UI 风格。
