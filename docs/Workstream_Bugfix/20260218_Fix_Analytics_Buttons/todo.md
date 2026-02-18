# 20260218_Fix_Analytics_Buttons - 修复分析面板按钮

## 背景 (Context)
用户报告在“转发详细统计”面板中，底部按钮（刷新、返回、关闭等）点击后没有反应或提示“开发中”。
经初步调查：
1. `AnalyticsMenuStrategy.ACTIONS` 虽然匹配了，但 `handle()` 方法由于并发冲突或逻辑缺失，部分动作直接被 `event.answer("开发中")` 拦截。
2. 之前的 `20260218_Fix_Analytics_Worker_Registry` 修复了 `history_task_list`，但未完全覆盖分析面板。

## 任务目标 (Tasks)
- [ ] 补全 `AnalyticsMenuStrategy` 中的 `detailed_analytics` 处理逻辑（映射回 `show_forward_analytics`）。
- [ ] 补全 `performance_analysis` 处理逻辑（映射回 `show_performance_analysis`）。
- [ ] 确保 `forward_analytics` 动作在 Controller 中正确分发。
- [ ] 验证按钮逻辑闭环。

## 技术路径 (Strategy)
1. 修改 `handlers/button/strategies/analytics.py`，将 Mock 的 `event.answer` 替换为正确的 Controller 调用。
2. 确保 `detailed_analytics` 调用 `menu_controller.show_forward_analytics(event)`。
3. 确保 `performance_analysis` 调用 `menu_controller.show_performance_analysis(event)`。
