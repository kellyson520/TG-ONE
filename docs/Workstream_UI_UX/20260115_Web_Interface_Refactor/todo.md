# Web 界面重构 (Web Interface Refactor)

## 背景 (Context)
用户要求重构 Web 端界面，使其更加简洁、高效、反应快且不卡顿。目前的界面使用了 Canvas 粒子背景和大量复杂的 CSS，可能在某些环境下表现欠佳。

## 策略 (Strategy)
1. **去繁就简**: 移除重型的 Canvas 粒子背景，改用轻量级的 CSS 渐变或微量装饰。
2. **现代化设计**: 使用更清晰的排版 (Typography)、一致的间距 (Spacing) 和现代的色调。
3. **性能优化**: 简化 CSS 选择器，减少重型滤镜 (如层叠的 blur) 的使用频率，改用更高效的实现方式。
4. **分步实施**: 遵循 `ui-ux-pro-max` 的 Overhaul 协议，分样式注入、结构调整、内容润色三个阶段实施。

## 待办清单 (Checklist)

### Phase 1: 样式注入 (Style Injection)
- [ ] 搜索现代 Dashboard 设计规范 (`ui-ux-pro-max`)
- [ ] 定义新的 Design Tokens (颜色、圆角、阴影、间距)
- [ ] 重构 `main.css` 核心变量与基础样式
- [ ] 优化按钮与表单控件的交互反馈

### Phase 2: 结构调整 (Structural Update)
- [ ] 更新 `base.html` 布局结构
- [ ] 移除 `particles-canvas` 并更新背景逻辑
- [ ] 优化侧边栏样式与动画

### Phase 3: 页面润色 (Page Polish)
- [ ] 重构 `dashboard.html` 核心组件
- [ ] 重构 `rules.html` 等关键功能页面
- [ ] 响应式适配优化 (Mobile/Tablet)

### Phase 4: 验证与验收 (Verify & Report)
- [ ] 全系统界面遍历检查
- [ ] 性能与卡顿测试 (浏览器性能分析)
- [ ] 生成交付报告 `report.md`
