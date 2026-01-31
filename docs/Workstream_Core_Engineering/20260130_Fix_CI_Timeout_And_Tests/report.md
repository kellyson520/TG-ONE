# Fix CI Timeout and Test Failures - Report

## 核心成就 (Summary)
成功修复导致 CI 单元测试超时的核心原因（测试套件挂起与资源泄漏），并解决了 Auth 模块的 CSRF 验证错误及 `conftest.py` 中的 Mock 与 Fixture 逻辑漏洞。

## 架构变更 (Architecture Refactor)
无重大业务架构变更，主要集中在测试基础设施的增强：
1.  **Conftest 增强**:
    -   重构 `setup_database` fixture，将 Setup 和 Teardown 的异常处理分离，彻底解决 generator 在 Teardown 阶段因异常二次 yield 导致的 `RuntimeError`，这是导致测试挂起/不稳定的主要原因。
    -   增强 `AsyncSafeMock`，使其递归返回 `AsyncMock` 而非默认的 `MagicMock`，解决了 `TypeError: object MagicMock can't be used in 'await' expression`，提升了对异步服务 Mock 的稳健性。

2.  **Auth 测试修复**:
    -   修复 `tests/integration/test_auth_router.py`，正确处理 CSRF Token 的持久化，使用 `client.cookies.get` 代替 Response Cookie（解决 `Response` 不一定每次都返回 Cookie 的问题）。

## 验证结果 (Verification)
手动运行的关键集成测试均已通过：
-   `tests/unit/core/`: <span style="color:green">PASSED</span> (0.89s) - 核心基础测试无阻塞。
-   `tests/integration/test_auth_router.py`: <span style="color:green">PASSED</span> (100%) - Auth/Login/Refresh 流程通过，无 CSRF 403 错误。
-   `tests/integration/test_security_phase3_api.py`: <span style="color:green">PASSED</span> (100%) - 2FA 流程及 IP Guard 测试通过，无 Fixture Error。

## 修复详情 (Details)
1.  **Auth CSRF Issue**: `test_refresh_token` 在调用 `/api/auth/refresh` 时使用了空的 CSRF Token，因为登录响应未返回新的 Cookie。改为从 `client.cookies` 获取持久化的 Token 后修复。
2.  **MagicMock Await Issue**: `conftest.py` 中的 `AsyncSafeMock` 在属性访问时默认返回 `MagicMock`。当被测试的一方尝试 `await` 该属性（例如 `await accessing_a_service_method`）时崩溃。现改为返回 `AsyncMock`。
3.  **Fixture Teardown Error**: `setup_database` 在 Resource Teardown 失败时再次 `yield`，违反生成器协议。分离 `try...except` 块后修复。

## 后续建议 (Recommendations)
-   建议在 CI 中增加 `-vv --durations=10` 参数，以便未来快速定位导致超时的具体慢测试。
-   定期检查 `conftest.py` 中的 Mock 逻辑，确保与业务层异步特性保持一致。
