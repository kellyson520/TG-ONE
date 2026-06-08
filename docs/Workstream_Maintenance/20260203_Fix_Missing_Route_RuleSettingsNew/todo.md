# Fix Missing Route: rule_settings:New

## 背景 (Context)
用户在设定转发规则后尝试打开规则页面时，由于服务层错误地返回了硬编码的 `"New"` 作为 `rule_id`，且路由系统未配置 `rule_settings:{id}` 路由，导致出现 "未找到路由处理程序" 的错误。

## 待办清单 (Checklist)

### Phase 1: 核心修复
- [x] 修复 `services/rule/logic.py` 中的 `bind_chat` 方法，使其返回真实的 `rule_id` 而不是 `"New"`
- [x] 在 `handlers/button/callback/callback_handlers.py` 中添加 `rule_settings:{id}` 路由映射
- [x] 检查 `RadixRouter` 对 `search_{rest}` 等非法占位符的处理，考虑是否需要优化路由规范

### Phase 2: 验证与报告
- [x] 运行单元测试验证 `bind_chat` 返回正确的 ID
- [x] 模拟 `rule_settings:123` 回调，验证路由分发是否成功
- [x] 生成任务报告
