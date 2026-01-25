# 单元测试架构方案 (Specification)

## 1. 技术栈
- **Runner**: `pytest`
- **Async Plugin**: `pytest-asyncio`
- **Mocking**: `unittest.mock` / `pytest-mock`
- **HTTP Client**: `httpx.AsyncClient` (针对 FastAPI)
- **DB**: `sqlite+aiosqlite:///:memory:` (内存数据库，隔离测试)

## 2. 目录结构
```text
tests/
  ├── conftest.py             # 全局 Fixtures (DB, Client, Loop)
  ├── unit/                   # 单元测试
  │   ├── models/
  │   ├── services/
  │   └── utils/
  └── integration/            # 集成测试
      ├── api/
      └── workflows/
```

## 3. 测试策略
### 3.1 数据库测试
- 使用内存 SQLite 数据库 (`sqlite+aiosqlite:///:memory:`) 进行测试，确保速度快且不污染真实数据。
- 使用 Fixture 在测试前后自动创建/销毁表结构。

### 3.2 依赖注入 (Dependency Injection)
- 利用 `core.container` 的覆盖能力或 FastAPI 的 `app.dependency_overrides`。
- 对于 Service 测试，Mock Repository 层。
- 对于 API 测试，可以 Mock Service 层，也可以运行真实 Service (集成测试)。

## 4. 命名规范
- 文件名: `test_*.py`
- 类名: `Test*`
- 函数名: `test_*`

---

# Phase 5.5: Handler Layer Import Debugging Spec (Source: DebugHandlerImports)

> **创建时间**: 2026-01-09 00:10
> **优先级**: P0 (阻塞测试)
> **目标**: 解决 Handler 层循环导入问题，完成单元测试

## 核心问题与解决方案
**核心问题**: `core/container.py` 的全局实例化导致循环导入。
**解决方案**: **方案 B: Mock Container** (快速解决)
- 在 `conftest.py` 中 Mock `core.container`。
- 长期优化将采用延迟实例化（`get_container()`）。

---

# Phase 2: Core Security Functionality Hardening Spec (Source: Security_Phase2)

> **Created**: 2026-01-09
> **Priority**: P1
> **Goal**: Implement robust session management and token refresh mechanisms.

## 🎯 Objectives
1.  **Token Refresh Mechanism**: Short-lived Access Tokens, Long-lived Refresh Tokens.
2.  **Session Management**: Track `ActiveSession` in DB, Remote Logout.
3.  **CSRF Protection**: Full integration for state-changing requests.

## 🛠️ Implementation Plan
1.  **Database**: Use `ActiveSession` table.
2.  **Service Layer**: `SessionService`, `AuthenticationService`.
3.  **API Layer**: `/auth/refresh`, `/auth/logout`, `/auth/sessions`.

