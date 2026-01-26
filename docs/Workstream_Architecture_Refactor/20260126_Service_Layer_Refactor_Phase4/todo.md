# Phase 4: Service Layer Refactoring and Utils "Cleanliness" Order

## 背景 (Context)
将分散在 Utils 的逻辑收归 Service，建立标准化的业务层。彻底消除 Utils 中的业务逻辑泄露，标准化目录结构。

## 待办清单 (Checklist)

### Phase 4.1: Utils 层业务逻辑歼灭战 (P1 - High) [DONE]
- [x] **解耦数据库**: 彻底移除 `utils/processing/` 对 `sqlalchemy` 的直接引用，通过 Repository 注入。
    - [x] 审计 `utils/processing/smart_dedup.py`
    - [x] 审计 `utils/processing/batch_processor.py` (已迁移为 batch_repo.py)
- [x] **业务下沉 - Task Service**: 将 `utils/processing/message_task_manager.py` 迁移至 `services/task_service.py`。
- [x] **业务下沉 - Queue Service**: 将 `utils/processing/forward_queue.py` 升级为 `services/queue_service.py`。
- [x] **业务下沉 - Search Service**: 将 `utils/helpers/search_system.py` 升级为 `services/search_service.py`。

### Phase 4.2: 目录结构标准化 (大一统) (P1 - High) [DONE]
- [x] **Repositories 迁移**: `utils/db/` -> `repositories/` (彻底移除混合在 utils 中的 DB 操作)。
- [x] **Network Services 迁移**: `utils/network/` -> `services/network/`。
- [x] **Core Helpers 迁移**: `utils/helpers/` -> `core/helpers/` (真正通用的纯函数)。
- [x] **Config 迁移**: `config/` (root) -> `core/config/` (消除根目录冗余)。

### Phase 4.3: Service 与 Util 领域重划 (P1 - High) [DONE]
- [x] **Menu Service**: 从 `controllers/menu_controller.py` 剥离业务逻辑。
- [x] **Filters 清洗**:
    - [x] `rss_filter.py`: I/O 逻辑移至 `services/rss_service.py`。
    - [x] `ai_filter.py`: 预处理移至 `media_service`。
- [x] **动态过滤链**: 将 `FilterMiddleware` 改为完全由 `FilterChainFactory` 驱动。

### Phase 4.4: RSS 模块归口统一 (P1 - High) [DONE]
- [x] **核心集成**: 核心逻辑及路由整合至 `web_admin` 与 `services/rss_service.py`。
- [x] **清理**: 删除 redundancy 冗余的 `rss/` 独立目录。
