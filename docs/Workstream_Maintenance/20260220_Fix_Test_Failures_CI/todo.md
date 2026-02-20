# Fix Test Failures (CI Pipeline)

## 背景 (Context)
CI 流水线中 `test_rule_management_service.py` 和 `test_session_dedup.py` 出现持续失败。
主要涉及 ORM 延迟加载 (`DetachedInstanceError`) 和测试 Mock 数据不完整。

## 待办清单 (Checklist)

### Phase 1: 故障诊断与调研
- [x] 重现 `test_rule_management_service.py` 失败
- [x] 重现 `test_session_dedup.py` 失败
- [x] 分析 `DetachedInstanceError` 根源 (确认是 `rule_syncs` 缺失)

### Phase 2: 核心实现与修复
- [x] 修复 `RuleRepository`: 在全局查询中增加 `selectinload(ForwardRule.rule_syncs)` 预加载
- [x] 修复 `test_session_dedup.py`: 修正 Mock Event 的 `sender_id` 类型及媒体 `id` 缺失问题
- [x] 修复 `stats_router.py`: 解决 E302 风格检查错误 (2 blank lines)

### Phase 3: 验证与闭环
- [x] 本地运行 `test_rule_management_service.py` 验证 100% 通过
- [x] 本地运行 `test_session_dedup.py` 验证 100% 通过
- [x] 清理调试日志文件
- [x] 提交任务报告
