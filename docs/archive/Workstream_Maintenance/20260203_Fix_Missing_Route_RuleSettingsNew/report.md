# 任务交付报告: 修复规则设置路由缺失与 rule_id 错误

## 摘要 (Summary)
修复了用户在创建转发规则后点击"打开设置"按钮出现的 "路由处理程序未找到 (rule_settings:New)" 错误。该问题是由服务层逻辑错误及路由配置不完整共同导致的。

## 修复内容 (Architecture Refactor)

### 1. 服务层逻辑修正
- **文件**: `services/rule/logic.py`
- **变更**: 在 `bind_chat` 方法中，修复了新规则创建后硬编码返回 `"New"` 作为 ID 的 Bug。现在会正确捕获 `create_rule` 返回的真实数据库 ID 并返回。

### 2. 回调调度系统增强
- **文件**: `handlers/button/callback/callback_handlers.py`
- **变更**:
    - 添加了 `rule_settings:{id}` 路由映射，确保通过 ID 访问规则设置时的分发正确性。
    - 修复了大量野生通配路由（如 `search_{rest}`, `media_settings{rest}` 等）缺失冒号分隔符的问题。根据 `RadixRouter` 的实现，占位符必须作为一个独立的被冒号分隔的 `part` 存在。此次修复统一将 `action{placeholder}` 更改为 `action:{placeholder}`。

## 验证结果 (Verification)

### 1. 路由分发验证
运行 `verify_router_fix.py` 验证通过：
- `rule_settings:123` -> 成功匹配 `callback_rule_settings`
- `new_menu:forward_hub` -> 成功匹配 `handle_new_menu_callback`
- `search:abc` -> 成功匹配 `handle_search_callback`

### 2. 逻辑一致性
通过代码审计确认 `bind_chat` 现在返回 `new_rule.id`，与 `rule_commands.py` 中的按钮构造逻辑对齐。

## 后续建议
- 建议对菜单系统进行一次全面的点击流测试，确保所有 `new_menu:` 相关的跳转在重构后依然有效。
- 考虑增强 `RadixRouter` 的健壮性，使其能够处理 `_` 或无分隔符的占位符（如果业务需要）。
