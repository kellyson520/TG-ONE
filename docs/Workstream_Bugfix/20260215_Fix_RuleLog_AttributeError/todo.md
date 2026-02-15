# Fix RuleLog AttributeError in AnalyticsService

## 背景 (Context)
用户报告在 `analytics_service.py` 的 `search_records` 方法中出现 `AttributeError: 'RuleLog' object has no attribute 'source_chat_id'`。
经检查，`RuleLog` 模型确实没有这些字段，这些字段属于关联的 `ForwardRule` 模型。

## 待办清单 (Checklist)

### Phase 1: 问题确认与修复
- [x] 验证 `RuleLog` 与 `ForwardRule` 模型结构
- [x] 修改 `analytics_service.py` 中的 `search_records` 方法以正确访问关联字段
- [x] 确保使用 `joinedload` 优化关联查询性能

### Phase 2: 验证与验收
- [x] 编写/运行针对性测试用例
- [ ] 验证 Web 管理端搜索功能 (受限于环境，通过单元测试验证)
- [x] 生成交付报告并归档
