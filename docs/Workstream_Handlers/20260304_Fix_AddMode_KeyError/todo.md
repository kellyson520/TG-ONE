# Fix AddMode KeyError Regression

## 背景 (Context)
用户报告在规则设置界面出现 `KeyError: <AddMode.BLACKLIST: 'blacklist'>`。
该错误发生在 `handlers/button/settings_manager.py` 中，原因是 `rule.add_mode` 作为 `RuleDTO` 字段是一个 Enum 对象，而 `RULE_SETTINGS` 字典的键是字符串。

## 待办清单 (Checklist)

### Phase 1: 核心修复
- [x] 修改 `handlers/button/settings_manager.py` 中的 `RULE_SETTINGS` 键或访问逻辑，兼容 Enum。
- [x] 检查并确保 `forward_mode`, `message_mode`, `is_preview`, `handle_mode` 等其他可能存在同样问题的字段。
- [x] 验证 `toggle_rule_setting` 在 `services/rule/logic.py` 中对非布尔值的处理逻辑。

### Phase 2: 验证与清理
- [x] 编写测试脚本验证 `RULE_SETTINGS` 和 `MEDIA_SETTINGS` 的键访问。
- [x] 运行本地 CI 检查。
- [x] 提交并报告。

### Phase 3: 归档
- [x] 生成报告 `report.md`。
- [x] 更新 `docs/process.md`。
