# Technical Specification: Core Infrastructure Cleanup (Phase 2)

## 1. 物理目录清理 (Directory Cleanup)
- **managers/**: 目前包含冗余逻辑。确认其内部逻辑是否已迁移至 `services/` 或 `repositories/`。若是，则直接删除。
- **zhuanfaji/**: 遗留统计目录，确认无活跃引用后删除。
- **ufb/**: 孤立 JSON 存储，逻辑需合并至 `remote_config_sync` 模块。

## 2. 依赖治理 (Dependency Governance)
- **Container Refactoring**:
    - 引入 `Dependency Provider` 模式。
    - 避免在 `__init__` 中进行繁重的 I/O 或循环导入。
    - 使用 `set_container()` 或注入方式打破双向依赖。
- **Event Bus Decoupling**:
    - 事件总线不应知道 `web_admin` 的具体实现。
    - 使用抽象基类或信号机制。

## 3. 启动序列优化 (Bootstrap & Lifecycle)
- **main.py**: 目前是上帝类（God Script）。
- **core/bootstrap.py**:
    - `setup_environment()`: 环境变量、配置文件读取。
    - `init_container()`: 容器初始化。
    - `start_services()`: 异步服务启动。
- **core/lifecycle.py**:
    - 统一管理 `Startup` 和 `Shutdown` 钩子。

## 4. 核心服务合并
- **StateManager**: 状态管理逻辑应下沉至 `services/state_service.py`。
- **AI Service**: 统一从 `ai/` 文件夹通过服务接口暴露，而不是直接由 Container 管理多个子 Provider。
