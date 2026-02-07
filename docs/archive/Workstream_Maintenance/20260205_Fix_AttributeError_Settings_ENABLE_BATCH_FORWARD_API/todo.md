# 修复 Settings 对象缺少 ENABLE_BATCH_FORWARD_API 属性的错误

## 背景 (Context)
用户报告在发送消息时遇到 `AttributeError: 'Settings' object has no attribute 'ENABLE_BATCH_FORWARD_API'`。
经调查，`core/config/__init__.py` 中的配置项被错误地命名为 `FORWARD_ENABLE_BATCH_API`，而 `services/queue_service.py` 和 `services/network/api_optimization_config.py` 中使用了 `ENABLE_BATCH_FORWARD_API`。

## 技术方案 (Strategy)
1. 将 `core/config/__init__.py` 中的 `FORWARD_ENABLE_BATCH_API` 重命名为 `ENABLE_BATCH_FORWARD_API` 以保持代码一致性并修复 AttributeError。
2. 同步更新 `tests/integration/test_flood_wait.py` 中的环境变量模拟名。

## 待办清单 (Checklist)

### Phase 1: 基础修复
- [x] 修改 `core/config/__init__.py`: 重命名配置项
- [x] 修改 `tests/integration/test_flood_wait.py`: 更新环境变量名

### Phase 2: 验证
- [x] 运行集成测试 `pytest tests/integration/test_flood_wait.py`
- [x] 验证其他使用该配置的地方是否存在冲突
