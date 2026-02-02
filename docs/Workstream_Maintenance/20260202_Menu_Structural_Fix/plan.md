# 实施计划：修复菜单系统架构不一致与缺失方法 (Implementation Plan)

## 背景 (Background)
在修复 `show_realtime_monitor` 报错的过程中，发现 `handlers/button/callback/new_menu_callback.py` 存在严重的架构冲突和技术债务：
1. **多重架构并存**：部分逻辑直接调用子模块，部分通过 `new_menu_system` 代理，部分尝试通过 `menu_controller` 处理。
2. **大量缺失方法**：`new_menu_callback.py` 中引用了大量 `menu_controller` 并不存在的方法（如 `start_history_task`, `rebuild_bloom_index` 等）。
3. **严重冗余**：存在大量完全重复的 `elif action == "..."` 逻辑块，导致代码难以维护且行为不确定。

## 目标 (Objectives)
- 统一回调处理逻辑，消除冗余分支。
- 补齐 `MenuController` 中缺失的业务逻辑方法。
- 确保所有菜单点击动作都有对应的处理器，不再报 `AttributeError`。

## 实施步骤 (Steps)

### Phase 1: MenuController 补全 (50%)
- [ ] 在 `controllers/menu_controller.py` 中补全历史任务处理方法 (`show_history_task_selector`, `start_history_task` 等)。
- [ ] 在 `controllers/menu_controller.py` 中补全系统维护方法 (`rebuild_bloom_index`, `run_db_archive_once` 等)。
- [ ] 确保 `MenuController` 方法与 `new_menu_callback.py` 中的调用签名一致。

### Phase 2: new_menu_callback.py 瘦身与纠错 (80%)
- [ ] 移除 `handle_new_menu_callback` 中的冗余逻辑，将其全部收口至 `callback_new_menu_handler`。
- [ ] 消除 `callback_new_menu_handler` 中的重复 `elif` 分支。
- [ ] 统一调用规范：对于业务逻辑，优先使用 `menu_controller`；对于纯视图切换，可以使用 `new_menu_system`。

### Phase 3: 验证 (100%)
- [ ] 检查所有修改后的方法调用。
- [ ] 验证关键流程（转发管理、历史任务、系统监控）。

## 预期产物 (Outcome)
- 一个干净、无冲突的 `new_menu_callback.py`。
- 一个功能完整的 `MenuController.py`。
- 消除所有已知的 `AttributeError`。
