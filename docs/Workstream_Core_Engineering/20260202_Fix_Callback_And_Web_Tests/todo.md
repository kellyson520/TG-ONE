# Fix Callback and Web Tests

## 背景 (Context)
解决 `test_callback_handlers.py` 中的 `AttributeError` 和 `RuntimeWarning`，以及 `web` 模块由于重构导致的 `ModuleNotFoundError` 和 `ResponseSchema` 属性错误。
目标是确保核心回调逻辑和 Web 管理接口的单元测试通过。

## 待办清单 (Checklist)

### Phase 1: Callback Handler 修复
- [x] 修复 `test_callback_handlers.py` 中的 `AsyncSessionManager` patch 路径
- [x] 解决 `AsyncMockMixin` 未 await 的警告
- [x] 验证 `TestCallbackHandlers`, `TestOtherCallback`, `TestAdminCallback`, `TestMediaCallback`

### Phase 2: Web Router 修复
- [x] 修复 `test_rule_router.py` 中的 引用路径 (`web_admin.routers.rule_router` -> `web_admin.routers.rules.*`)
- [x] 修复 `test_system_router.py` 中的 引用路径 (`web_admin.routers.system_router` -> `web_admin.routers.system.*`)
- [x] 更新 router 测试中的断言逻辑，适配 `ResponseSchema` (使用 `.success` 而非 `.status_code`)
- [x] 修复 `test_rule_router.py` 中的依赖注入 (`Depends` 无法在直接调用中自动解析)

### Phase 3: 验证
- [x] 运行 `pytest tests/unit/handlers/test_callback_handlers.py` 通过
- [x] 运行 `pytest tests/unit/web/test_rule_router.py` 通过
- [x] 运行 `pytest tests/unit/web/test_system_router.py` 通过
