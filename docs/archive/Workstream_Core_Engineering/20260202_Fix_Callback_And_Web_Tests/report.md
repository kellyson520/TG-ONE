# 测试修复报告

## 任务摘要
本次任务专注于修复 `handlers` 和 `web` 模块的单元测试失败。主要涉及 `test_callback_handlers.py`、`test_rule_router.py` 和 `test_system_router.py`。

## 修复内容

### 1. Callback Handlers
*   **问题**: 测试失败，出现 `AttributeError` 和 `RuntimeWarning: coroutine ... was never awaited`。
*   **原因**:
    *   `AsyncSessionManager` 的 mocking 路径不匹配。
    *   部分 `AsyncMock` 对象在使用时未被正确 await。
*   **修复**:
    *   调整 patch 目标，确保正确 mock 数据库会话。
    *   (验证通过) 所有 callback 相关测试用例均已通过。

### 2. Web Rule Router
*   **问题**: `ModuleNotFoundError` 和 `AttributeError: 'ResponseSchema' has no attribute 'status_code'`。
*   **原因**:
    *   项目结构重构后，`web_admin.routers.rule_router` 已被拆分至 `web_admin.routers.rules.rule_crud_router` 等子模块。
    *   API 返回类型统一为 `ResponseSchema`，测试代码仍沿用旧的 `JSONResponse` 断言方式。
    *   pytest直接调用异步试图函数时，FastAPI的 `Depends` 依赖注入不会自动触发，导致参数为 `Depends` 对象而非实例。
*   **修复**:
    *   更新了测试文件中的 import 路径。
    *   手动 Mock 并注入 `rule_repo`, `stats_repo`, `service` 等依赖。
    *   更新断言逻辑，检查 `response.success` 和 `response.data`。
    *   (验证通过) `test_rule_router.py` 测试通过。

### 3. Web System Router
*   **问题**: 同样的 `ModuleNotFoundError`。
*   **原因**: `web_admin.routers.system_router` 已拆分为 `web_admin.routers.system.*`。
*   **修复**:
    *   更新 import 路径。
    *   更新 Router 前缀和注册检查。
    *   (验证通过) `test_system_router.py` 测试通过。

## 验证结果

所有目标测试套件均已通过，且符合内存使用规范。

```
tests/unit/handlers/test_callback_handlers.py ... PASSED
tests/unit/web/test_rule_router.py ... PASSED
tests/unit/web/test_system_router.py ... PASSED
```
