# Fix RuleRepository AttributeError

## 背景 (Context)
用户报告在 `services/rule/query.py` 中出现 `AttributeError: 'RuleRepository' object has no attribute 'get_all_rules_with_chats'`。
这导致无法获取所有包含聊天信息的转发规则。

## 待办清单 (Checklist)

### Phase 1: 问题诊断
- [x] 检查 `services/rule/query.py` 的调用位置
- [x] 检查 `repositories/rule_repo.py` 中的 `RuleRepository` 定义
- [x] 确认该方法是否被重命名或在重构中遗漏

### Phase 2: 修复方案
- [x] 在 `RuleRepository` 中实现 `get_all_rules_with_chats` 方法
- [x] 确保方法返回正确的规则和关联的聊天数据
- [x] 验证 `services/rule/query.py` 能够正常调用

### Phase 3: 验证与验收
- [x] 运行相关的单元测试
- [x] 检查是否有其他缺失的方法
- [x] 生成任务报告
