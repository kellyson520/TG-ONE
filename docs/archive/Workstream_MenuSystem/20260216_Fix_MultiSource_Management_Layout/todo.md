# 优化多源管理布局 (Optimize Multi-Source Management Layout)

## 背景 (Context)
用户反馈“多源管理”面板目前的显示方式与“规则管理”重复，都是点击进入详细设置。用户希望“多源管理”能体现“快速启用/关闭”的功能，按钮显示应改为“启用 规则五 A→B”这种形式，点击即切换状态。

## 待办清单 (Checklist)

### Phase 1: 现状调研与方案设计
- [x] 分析 `rules_menu.py` 中的 `show_multi_source_management` 实现
- [x] 分析 `RuleController.toggle_status` 的业务逻辑与重定向
- [x] 设计新的按钮文案与回调逻辑

### Phase 2: 代码实现
- [x] 修改 `rules_menu.py` 中的 `show_multi_source_management`：
    - [x] 获取规则详情以确定其当前状态
    - [x] 按钮改为：`🟢 开启中` / `🔴 已关闭` 格式
    - [x] 回调动作改为 `new_menu:toggle_rule:{id}:multi:{page}`
- [x] 修改 `handlers/button/strategies/rules.py`：
    - [x] 增加对 `toggle_rule` 携带来源标识（如 `multi`）的处理
- [x] 修改 `RuleController.toggle_status`：
    - [x] 支持根据来源参数刷新不同的页面

### Phase 3: 验证与验收
- [x] 验证点击按钮后规则状态是否切换
- [x] 验证切换后菜单是否正确刷新并留在原页面
- [x] 提交报告并归档
