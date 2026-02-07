# 升级时间范围选择和日期选择页面 (Upgrade Date Picker)

## 背景 (Context)
用户要求升级 Telegram 机器人中的时间/日期选择器，采用更高级的“滚轮式旋转选择”交互方式，并支持精确到秒的完整时间显示（如：2000年12月1日21时22分38秒）。日期范围应从系统/会话的最早时间开始。

## 待办清单 (Checklist)

### Phase 1: 规划与设计 (Plan & Design)
- [x] 分析现有 `PickerMenu` 逻辑并设计“滚轮”式 UI 布局
- [x] 确定最早会话时间的获取方式
- [x] 编写接口规范 (Spec)

### Phase 2: 核心组件实现 (Build)
- [x] 实现滚轮选择器逻辑 (Picker Wheel Logic)
- [x] 实现动态生成年、月、日、时、分、秒的选择按钮
- [x] 实现时间范围选择器的升级版页面
- [x] 保持向前兼容，适配现有的 `SessionService` 参数

### Phase 3: 集成与优化 (Integrate)
- [x] 在 `picker_menu.py` 中更新相關方法
- [x] 在 `new_menu_callback.py` 中注册新的回调处理逻辑
- [x] 优化 UI 视觉效果，确保“高级感”

### Phase 4: 验证与报告 (Verify & Report)
- [x] 手动/半自动测试时间选择的准确性
- [x] 验证起始日期的正确性
- [x] 生成交付报告 `report.md`
