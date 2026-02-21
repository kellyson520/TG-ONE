# 修复 AdminLogs 缺失与 Invalid Message ID 错误

## 背景 (Context)
解决以下三个核心 Bug：
1. `AttributeError: 'MenuController' object has no attribute 'show_admin_logs'`：后台菜单策略中找不到显示日志的方法。
2. `Action 'admin_logs' has been unmatched`：按钮动作未路由。
3. `The specified message ID is invalid or you can't do that operation on such message`：转发任务中消息 ID 失效。

## 待办清单 (Checklist)

### Phase 1: 问题诊断 (Diagnosis)
- [x] 审计 `MenuController` 及其 Mixins，确认 `show_admin_logs` 是否存在
- [x] 审计 `handlers/button/strategies/admin.py` 中的动作映射
- [x] 审计 `middlewares/sender.py` 中 `ForwardMessagesRequest` 的调用逻辑与异常处理

### Phase 2: 代码实现 (Implementation)
- [x] 在 `MenuController` 或其相关组件中实现 `show_admin_logs`
- [x] 修复 `AdminMenuStrategy` 中的动作路由
- [x] 优化 `sender` 中转发逻辑，增加消息 ID 有效性校验或异常捕获

### Phase 3: 验证与验收 (Verification)
- [x] 运行相关单元测试
- [x] 验证后台日志显示功能
- [x] 验证转发失败时的自愈或清理逻辑
