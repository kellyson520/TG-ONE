# 修复 Settings 对象缺少 ENABLE_BATCH_FORWARD_API 属性的错误报告

## 摘要 (Summary)
修复了由于配置项命名不一致导致的 `AttributeError: 'Settings' object has no attribute 'ENABLE_BATCH_FORWARD_API'`。将 `core/config/__init__.py` 中的 `FORWARD_ENABLE_BATCH_API` 重命名为 `ENABLE_BATCH_FORWARD_API`，确保与业务逻辑代码一致。

## 架构变更 (Architecture Refactor)
- **配置层**: 统一了批量转发 API 的配置项名称。

## 验证结果 (Verification)
- **集成测试**: `pytest tests/integration/test_flood_wait.py` 通过。
  - `test_batch_forward_fallback` 成功验证了在 `ENABLE_BATCH_FORWARD_API` 开启下的行为及回退逻辑。
- **静态检查**: `grep` 确认所有 active code 中均已使用新名称，且无陈旧引用（除 archive 外）。

## 操作指南 (Manual)
- 如果是在 `.env` 文件中配置了此项，请将 `FORWARD_ENABLE_BATCH_API` 更改为 `ENABLE_BATCH_FORWARD_API`。默认为 `True`。
