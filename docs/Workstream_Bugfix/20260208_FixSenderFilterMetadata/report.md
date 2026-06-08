# 任务完成报告: 修复 SenderFilter MessageContext 缺失 metadata 属性错误

## 任务背景 (Summary)
用户反馈在消息处理过程中，`SenderFilter` 报错：`'MessageContext' object has no attribute 'metadata'`。经分析，这是由于 `filters/context.py` 中的 `MessageContext` 类（使用了 `__slots__`）未包含 `metadata` 属性，而 `SenderFilter` 升级后开始使用该属性存储解析后的目标 ID。

## 修复内容 (Architecture Refactor)
1. **修改 `filters/context.py`**:
   - 在 `MessageContext` 的 `__slots__` 中添加 `'metadata'`。
   - 在 `__init__` 方法中初始化 `self.metadata = {}`。
2. **验证**:
   - 编写了 `tests/unit/filters/test_fix_metadata.py`，成功复现并验证了修复效果。

## 验证结果 (Verification)
- **单元测试**: `tests/unit/filters/test_fix_metadata.py` 通过。
- **日志验证**: `pytest` 运行结果显示 `metadata` 已能正常存储解析后的目标 ID。

## 后续建议
- 项目中存在两个 `MessageContext` 类（`filters/context.py` 和 `core/pipeline.py`），未来应考虑统一为一个标准的消息上下文类，以避免类似的属性不一致问题。

## 质量矩阵 (Quality Matrix)
- [x] 代码符合 `__slots__` 约束
- [x] 修复了 `AttributeError`
- [x] 新增测试用例覆盖修复场景
