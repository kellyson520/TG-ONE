# 修复转发详细统计显示为空 (Fix Forward Stats Empty Display)

## 背景 (Context)
用户反馈“转发详细统计”页面所有数据均显示为 0 或占位符（?），主要表现为：
- 周期显示为 `? 至 ?`
- 总计、失败、日均转发均为 0
- 热门规则 ID 存在但计数为 0

## 策略 (Strategy)
经过初步分析，原因是 `AdminController` 调用了错误的 Service 方法 (`get_detailed_stats`)，该方法返回的数据结构与 `MainMenuRenderer.render_forward_analytics` 预期的结构不匹配（缺少 `period` 和 `summary` 字段，且 `top_rules` 键名不一致）。
修复方案：
1. 将 `AdminController` 中的调用改为 `get_detailed_analytics`。
2. 统一 `AnalyticsService` 与 `Renderer` 的数据契约。
3. 清理 `AdminController` 中的同名重复函数。

## 待办清单 (Checklist)

### Phase 1: 规划与分析
- [x] 确定问题根源：`AdminController` 调用了结构不匹配的 API
- [x] 更新项目总进度文档 `docs/process.md`

### Phase 2: 代码修复
- [x] 优化 `AnalyticsService.get_detailed_analytics` 确保数据准确性
- [x] 修改 `AdminController.show_forward_analytics` 调用正确的 Service 接口
- [x] 移除 `AdminController` 中的冗余重复方法
- [x] 检查 `ui/menu_renderer.py` 确保它正确代理了 `MainMenuRenderer`

### Phase 3: 验证
- [x] 编写模拟脚本或单元测试验证数据渲染逻辑
- [x] 检查所有统计字段是否已正确填充

### Phase 4: 交付与归档
- [ ] 生成 `report.md`
- [ ] 更新 `process.md` 状态为 100%
- [ ] 清理临时文件
