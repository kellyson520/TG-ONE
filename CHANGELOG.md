# Change Log

## 📅 2026-01-25 更新摘要

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
