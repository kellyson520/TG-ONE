# 任务待办：修复菜单系统回调错误 (Fix Menu Callback Error)

## 问题描述 (Problem)
用户反馈在点击新菜单中的实时监控时报错：
`'NewMenuSystem' object has no attribute 'show_realtime_monitor'`
经查，`show_realtime_monitor` 实际上实现在 `MenuController` 中，但在 `new_menu_callback.py` 的部分逻辑中错误地在 `new_menu_system` 对象上调用了该方法。

## 修复策略 (Strategy)
1. 统一回调逻辑：修正 `handlers/button/callback/new_menu_callback.py` 中对 `show_realtime_monitor` 的调用，重定向至 `menu_controller`。
2. 清理冗余逻辑：检查并处理 `new_menu_callback.py` 中重复的 `action == "realtime_monitor"` 处理块。
3. 增强稳健性：对关键回调增加异常捕获和友好提示。

## 待办事项 (Checklist)
- [x] 备份并修改 `handlers/button/callback/new_menu_callback.py`
- [x] 验证 `realtime_monitor` 按钮功能 (通过逻辑校验与冗余清理)
- [x] 检查并处理其他潜在的缺失方法 (如 `show_failure_analysis`, `export_csv`)
- [x] 确认 `analytics_menu.py` 中的按钮定义与控制器一致
- [x] 提交修复报告
