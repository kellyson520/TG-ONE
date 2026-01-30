# 20260129_Fix_Remaining_Integration_Tests

## 背景 (Context)
在完成 UserHandler 重构后的测试适配过程中，发现部分集成测试仍然存在错误。
特别是 `tests/integration/test_web_full_link.py` 存在 `KeyError: 'rule_id'`，导致 CI 失败。
需要修复这些残余的测试错误，确保系统全链路稳定性。

## 策略 (Strategy)
1. 修复 API 响应结构不匹配导致的 `KeyError`。
2. 运行并验证 `tests/integration/` 下的关键测试用例。
3. 确保本地 CI 执行无误。

## 待办清单 (Checklist)

### Phase 1: 修复 Web Full Link 集成测试
- [ ] 修复 `test_web_full_link.py` 中的 `KeyError: 'rule_id'` (由于响应嵌套导致)
- [ ] 验证 `test_web_full_link.py` 全量通过

### Phase 2: 验证核心消息链路
- [ ] 运行 `pytest tests/integration/test_message_flow.py` 确保通过
- [ ] 运行 `pytest tests/integration/test_pipeline_flow.py` 确保通过

### Phase 3: 全量回归与闭环
- [ ] 运行本地 CI (`python scripts/local_ci.py`)
- [ ] 生成任务报告 `report.md`
