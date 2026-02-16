# 修复转发中心按钮 (Fix Forward Hub Buttons)

## 背景 (Context)
用户反馈“转发管理中心”面板中的部分按钮（详细统计、全局筛选、性能监控）点击后显示“开发中”，无法正常使用。这些功能在底层模块中已有初步实现，但未在回调策略中正确对接。

## 待办清单 (Checklist)

### Phase 1: 现状调研与方案设计
- [x] 定位所有显示“开发中”的按钮动作
- [x] 确认底层渲染器和菜单模块的对应关系
- [x] 设计对接方案

### Phase 2: 代码实现
- [x] 修改 `handlers/button/strategies/rules.py` 对接 `forward_stats_detailed`
- [x] 修改 `handlers/button/strategies/rules.py` 对接 `global_forward_settings`
- [x] 修改 `handlers/button/strategies/rules.py` 对接 `forward_performance`
- [x] 检查并确保 `forward_search` 逻辑闭环

### Phase 3: 验证与验收
- [x] 运行相关单元测试（如果存在）
- [x] 检查新菜单系统的分发逻辑是否正常
- [x] 提交报告并归档

## 进度说明
- 2026-02-16: 初始化任务，识别出 `RuleMenuStrategy` 中的 stub 逻辑。
