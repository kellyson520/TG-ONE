# 任务清单: 修复刷新转发中心失败问题

## 背景 (Context)
用户在点击“刷新数据”按钮时遇到错误：`MenuController.show_forward_hub() got an unexpected keyword argument 'force_refresh'`。
这是由于 `show_forward_hub` 方法未定义 `force_refresh` 参数，但调用方传入了该参数。

## 待办清单 (Checklist)

### Phase 1: 问题诊断
- [x] 在 `MenuController` 中查找 `show_forward_hub` 定义。
- [x] 确认 `new_menu_callback.py` 中的调用逻辑。

### Phase 2: 核心修复
- [x] 修改 `MenuController.show_forward_hub` 以支持 `force_refresh` 参数。
- [x] 修改 `MenuService.get_forward_hub_data` 以支持并传递 `force_refresh` 参数。
- [x] 在 `new_menu_callback.py` 中分发 `refresh_forward_hub` 动作。

### Phase 3: 验证与验收
- [x] 验证回调逻辑注入成功。
- [x] 更新 `report.md` 和 `process.md`。
