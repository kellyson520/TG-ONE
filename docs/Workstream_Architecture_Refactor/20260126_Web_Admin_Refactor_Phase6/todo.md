# Phase 6: Web Admin 与表现层重构 (P1/P2)

## Context
目标：标准化 API 接口，拆分庞大的路由文件，移除 `fastapi_app.py` 剩余 API，纯净化表现层。

## Strategy
*   Refactor `web_admin/routers` by splitting `system_router.py` and `rule_router.py`.
*   Purify `handlers` and `ui` by separating logic and presentation.
*   Enforce `ResponseSchema` and dependency injection (`Depends`) in routers.

## Phased Checklist

### Phase 1: Router Decomposition & API Modernization
* [x] **Web 路由器拆解 (`web_admin/routers/`)**
    * [x] **拆解 `system_router.py`**: 提取 `log_router.py`, `maintain_router.py`, `stats_router.py`。
    * [x] **拆解 `rule_router.py`**: 提取 DTO 映射逻辑至 `RuleDTOMapper`。
* [x] **API 现代化**
    * [x] 移除 `fastapi_app.py` 中的剩余 API。
    * [x] 确保所有新路由注册到 `web_admin/fastapi_app.py`。

### Phase 2: Prevention Layer Purification & Security
* [x] **表现层纯净化**
    * [x] 为所有路由引入 `ResponseSchema`，标准化 JSON 返回结构。
    * [x] 撤销路由对 `Container` 的直接访问，改用 `Depends` 注入 (Service Injection)。
* [x] **安全与认证**
    * [x] 移除手动认证，统一通过 `deps` 依赖。

### Phase 3: Handler & UI Decomposition
* [x] **Handler 拆分**
    * [x] `handlers/button/callback/callback_handlers.py`: 垂直拆分为 `modules/*.py`。
* [x] **UI 渲染器细化**
    * [x] `ui/menu_renderer.py`: 细化为多个专用渲染器 (e.g., `RuleMenuRenderer`, `SettingsMenuRenderer`)。
