# 修复 AddMode KeyError 错误

## 背景 (Context)
用户在点击规则设置按钮时遇到 `KeyError: 'blacklist'` 错误。根因是 `settings_manager.py` 中 `RULE_SETTINGS['add_mode']['values']` 字典使用枚举对象作为键，但数据库中存储的是字符串值。

## 策略 (Strategy)
将 `RULE_SETTINGS['add_mode']['values']` 和其他类似配置的字典键从枚举对象改为字符串值，与数据库存储格式保持一致。

## 待办清单 (Checklist)

### Phase 1: 分析与定位
- [x] 定位错误堆栈
- [x] 检查 `AddMode` 枚举定义
- [x] 检查 `RULE_SETTINGS` 配置
- [x] 确认数据库存储格式

### Phase 2: 修复实现
- [x] 修改 `RULE_SETTINGS['add_mode']['values']` 字典键为字符串
- [x] 修改 `RULE_SETTINGS['forward_mode']['values']` 字典键为字符串
- [x] 修改 `RULE_SETTINGS['message_mode']['values']` 字典键为字符串
- [x] 修改 `RULE_SETTINGS['is_preview']['values']` 字典键为字符串
- [x] 修改 `RULE_SETTINGS['handle_mode']['values']` 字典键为字符串
- [x] 修改 `MEDIA_SETTINGS['extension_filter_mode']['values']` 字典键为字符串

### Phase 3: 验证
- [x] 检查是否还有其他类似问题
- [x] 本地测试规则设置功能
- [x] 确认所有按钮显示正常

### Phase 4: 文档更新
- [x] 更新 `process.md`
- [x] 生成 `report.md`
