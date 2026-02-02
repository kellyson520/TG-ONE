# 菜单系统架构修复报告

## 📅 完成日期
2026-02-02

## 📝 任务目标
解决 `new_menu_callback.py` 在菜单回调处理中直接调用 `new_menu_system` 不存在方法导致的 `AttributeError`，并清理冗余代码，逐步将业务逻辑迁移至 `MenuController`。

## ✅ 完成内容

### 1. 修复核心 `AttributeError` 问题
- **原因**: `new_menu_callback.py` 中多处代码试图调用 `new_menu_system.show_analytics_hub`, `new_menu_system.show_forward_hub` 等方法，但这些方法未在 `NewMenuSystem` 类中定义。
- **解决方案**: 修改 `new_menu_callback.py`，将这些非法调用替换为 `MenuController` 中已经存在的对应方法 (`show_analytics_hub`, `show_forward_hub`, `show_dedup_hub`, `show_system_hub`)。

### 2. 补全 `MenuController` 缺失方法
为支持新架构，在 `controllers/menu_controller.py` 中补充了如下方法：
- `rebuild_bloom_index(event)`: 处理 Bloom 索引重建请求。
- `run_db_archive_once(event)`: 执行单次归档任务。
- `run_db_archive_force(event)`: 执行强制归档任务。
- `show_current_chat_rules(event, chat_id)`: 显示当前会话的规则列表。
- `show_current_chat_rules_page(event, chat_id, page)`: 分页显示当前会话的规则列表。
- `show_rule_management(event, page)`: 显示转发规则管理中心。
- `show_history_task_list(event)`: 原定占位，现已添加基础实现。

### 3. 代码重构与去重
- **移除冗余**: 删除了 `new_menu_callback.py` 中重复定义的 `action == "media_types"` 逻辑块。
- **简化入口**: 重构 `handle_new_menu_callback` 函数，使其成为统一入口，将所有逻辑委托给 `callback_new_menu_handler`，并移除了内部冗余的分发逻辑。
- **逻辑统一**: 确保所有 "Hub" 类操作（数据中心、去重中心、系统设置等）以及规则管理相关操作都通过 `MenuController` 进行路由。

### 4. 验证
- 通过 `verify_menu_methods.py` 脚本验证了 `MenuController` 已具备所有被调用的关键方法。
- 确认不再存在调用 `new_menu_system.show_analytics_hub` 等不存在方法的代码路径。

## ⚠️ 下一步建议
- 监控日志，确认是否还有其它遗漏的回调 action。
- 继续将 `NewMenuSystem` 退化为纯 View 层，移除其中仅作为代理存在的业务逻辑代码。
