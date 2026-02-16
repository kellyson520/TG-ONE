# 任务报告: 多源管理布局优化 (Report: Multi-Source Management Layout Optimization)

## 任务概况
- **任务目标**: 将“多源管理”重构为“快速开关”面板，使用户能够直接在视图中一键启用/关闭规则，并在操作后自动刷新返回原页面。
- **状态**: 100% 完成
- **日期**: 2026-02-16

## 变更详情
1. **视图层改进 (`RulesMenu`)**:
   - `show_multi_source_management` 按钮文案升级：使用 `🟢 开启中` 和 `🔴 已关闭` 明确标识状态。
   - 增加动作前缀，使用户明确点击后的预期。
   - 回调 Data 注入 `multi` 标识和当前 `page`。

2. **逻辑分发改进 (`RuleMenuStrategy`)**:
   - `toggle_rule` 动作现在支持解析 `extra_data`，识别请求来源 (`detail` vs `multi`)。

3. **控制器逻辑增强 (`RuleController`)**:
   - `toggle_status` 方法支持可选的 `from_page` 参数。
   - 操作完成后，根据来源自动路由：如果是从多源管理进入，则刷新返回多源管理列表页。

## 验证结果
- **交互验证**: 点击按钮后，规则状态立即切换，Bot 发出切换成功的通知，并迅速刷新回当前页码的多源管理列表。
- **视觉验证**: 状态图标实时更新，文案清晰易懂。

## 架构合规性
- 遵循 PSB 系统工作流。
- 保持了 Handler 的纯净，逻辑集中在 Controller。
