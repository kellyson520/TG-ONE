# Phase 4 Refactoring Specification

## 1. 业务逻辑下沉方案 (Service Migration)

### 1.1 `TaskService`
- **原文件**: `utils/processing/message_task_manager.py`
- **目标**: `services/task_service.py`
- **调整**: 
  - 接入 `Container` 进行 DI。
  - 移除对全局变量的依赖。

### 1.2 `QueueService`
- **原文件**: `utils/processing/forward_queue.py`
- **目标**: `services/queue_service.py`
- **调整**: 
  - 统一异步队列管理。
  - 支持优先级和背压。

### 1.3 `SearchService`
- **原文件**: `utils/helpers/search_system.py`
- **目标**: `services/search_service.py`
- **调整**: 
  - 隔离 `LocalSearch` 和 `RemoteSearch` Provider。
  - 统一搜索接口。

## 2. 目录标准化映射 (Directory Remapping)

| 原路径 | 新路径 | 备注 |
| :--- | :--- | :--- |
| `utils/db/` | `repositories/` | 命名规范：`xxx_repository.py` |
| `utils/network/` | `services/network/` | 网络链路相关服务 |
| `utils/helpers/` | `core/helpers/` | 仅保留无副作用的工具函数 |
| `config/` | `core/config/` | 移除根目录噪音 |

## 3. 分层规范 (Layering Rules)

- **Handlers**: 仅限 UI/交互逻辑。
- **Services**: 业务逻辑主体。
- **Repositories**: 数据持久化，仅通过 DTO 交互。
- **Core**: 基础设施、辅助工具、配置。

## 4. 实施策略 (Implementation Strategy)

1. **Move & Wrap**: 先移动文件，建立 wrapper 或 alias 确保不破坏现有调用。
2. **Refactor**: 逐步清理内部的业务违规（如 ORM 泄露）。
3. **Delete**: 确认无误后删除旧文件。
