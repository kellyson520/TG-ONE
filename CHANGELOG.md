# Change Log

## 📅 2026-01-26 更新摘要

### 🚀 v1.2.2.1: Dynamic Pipeline & Controller Decoupling (Phase 4)
- **God-Class Decoupling (MenuController)**:
    - Stripped all direct SQLAlchemy dependencies and repository calls from `MenuController`.
    - Offloaded state management to `SessionService` (via `update_user_state`).
    - Delegated Rule CRUD and logic to `RuleManagementService` (implementing `clear_keywords` and `clear_replace_rules`).
    - Centralized view-model preparation in `MenuService`.
- **Full Dynamic Filter Pipeline**:
    - Replaced hardcoded middleware registry with `FilterChainFactory`.
    - Enabled per-rule dynamic assembly: Filters are now instantiated on-demand based on DB flags (e.g., `is_ai`, `only_rss`, `enable_delay`).
    - Added `process_context` to `FilterChain` to support externally injected `MessageContext`.
- **Circular Dependency & Import Hygiene**:
    - Resolved critical blocking import loops in `SenderFilter`, `AIFilter`, and `RSSFilter` by pivoting to **Lazy Local Imports**.
    - Verified clean import tree using the new `scripts/debug_import.py` utility.
- **RSS Strategy Consolidation**:
    - Eliminated the redundant legacy `rss/` root directory.
    - Unified all feed generation and media harvesting into `services/rss_service.py` using `aiohttp` (when available).
- **Test Matrix & Verification**:
    - Implemented `tests/integration/test_dynamic_filter_chain.py` verifying assembly logic for Basic, AI, and RSS-only rules.
    - Refactored legacy `tests/integration/test_pipeline_flow.py` to use `filter_registry_mock` via `unittest.mock.patch`, ensuring support for the new factory architecture.



## 📅 2026-01-25 更新摘要

### 🚀 v1.2.2: Pipeline Integrity & Stability (Phase 3+)
- **Integration Tests**: Achieved 100% pass rate for Core Pipeline (Loader -> Dedup -> Filter -> Sender) with `pytest tests/integration/test_pipeline_flow.py`.
- **Model Integrity**: Restored 30+ missing fields in `ForwardRule` ORM model, ensuring exact parity with DTOs and preventing data loss.
- **Resilience**: Fixed naked `raise` in `QueueService` retry loop; Verified Circuit Breaker and Dedup Rollback mechanisms under simulated network failure.
- **Config**: Consolidated missing DB/RSS settings into `core.config`.
- **Testing**: Enhanced mock infrastructure for `mock_client.forward_messages` and `MessageContext` state tracking.

### 🚀 v1.2.1: Data Security & Core Purge (Phase 3 Completed)
- **Security**: Established a strict DTO barrier in Repository layer; ORM models are now shielded from Services and Handlers.
- **Pure Functions**: Monolithic `utils/helpers/common.py` logic migrated to `UserService` and `RuleFilterService`.
- **Domain Refinement**: Split `rule_service.py` into `query.py` and `filter.py` within `services/rule/` domain.
- **Compatibility**: Implemented Legacy Proxies for `rule_service` and `rule_management_service` for seamless transition.
- **Verification**: Built comprehensive unit tests for `UserService` and stabilized `Rule` domain tests.

### 🚀 v1.2.0: Core Architecture Overhaul (Phase 3)
- **Models**: Split monolithic `models.py` into `rule`, `chat`, `user` domains.
- **Services**: Refactored `RuleManagementService` into Facade/Logic/CRUD layers.
- **Repository**: Created `RuleRepository` with W-TinyLFU caching.
- **Database**: Introduced Alembic for migrations; fixed SQLite Enum bindings.
- **Engineering**: Added Windows Platform Adapter skill; strictly enforced Service vs Repository layering.

### ♻️ 重构 (Phase 2)
- **core**: comprehensive infrastructure cleanup, verification, and bug fixes in Phase 2 (f068592) @kellyson520

### 🔧 工具/文档
- **init**: initial commit (c989f4a) @kellyson520
