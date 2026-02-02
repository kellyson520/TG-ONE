# 2026-02-02 菜单系统架构修复任务

## 📝 任务描述
修复菜单系统中的结构性问题，包括 `AttributeError` 错误、重复代码以及 `MenuController` 缺失的方法。目标是确保 `new_menu_callback.py` 通过 `MenuController` 统一调用，消除对 `NewMenuSystem` 不存在方法的调用，并补全缺失的业务逻辑接口。

## ✅ 已完成
- [x] 修复 `AttributeError: show_analytics_hub` (移除错误调用，改用 `MenuController`)
- [x] 修复 `AttributeError: show_forward_hub` (移除错误调用，改用 `MenuController`)
- [x] 修复 `AttributeError: show_current_chat_rules` (移除错误调用，并在 `MenuController` 中实现对应方法)
- [x] 在 `MenuController` 中实现缺失的维护方法:
    - [x] `rebuild_bloom_index`
    - [x] `run_db_archive_once`
    - [x] `run_db_archive_force`
- [x] 在 `MenuController` 中实现缺失的显示方法:
    - [x] `show_current_chat_rules`
    - [x] `show_current_chat_rules_page`
    - [x] `show_rule_management`
    - [x] `show_history_task_list`
- [x] 重构 `new_menu_callback.py`:
    - [x] 移除重复的 `media_types` 处理逻辑
    - [x] 简化 `handle_new_menu_callback` 入口逻辑
    - [x] 统一 Hub 调用及其它回调到 `MenuController`
- [x] 验证 `menu_controller.py` 和 `new_menu_system.py` 方法一致性

## 🚧 待办事项
- [ ] (可选) 进一步清理 `NewMenuSystem` 中不再使用的代理方法
- [ ] (可选) 完善 `MenuController` 的 Type Hinting
