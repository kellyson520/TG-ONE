# Core Infrastructure Cleanup (Phase 2)

## 背景 (Context)
执行架构重构的第二阶段，重点在于清理 Legacy 代码、解决循环依赖、重构启动流程以及合并核心组件。这是确保系统稳定性和可维护性的关键 P0 任务。

## 待办清单 (Checklist)

### Phase 1: 物理目录歼灭战 [P0]
- [ ] 删除 `managers/` 及其目录下所有 Legacy 代码。
- [ ] 删除 `zhuanfaji/` 冗余统计目录。
- [ ] 删除 `ufb/` 目录，消除磁盘上的孤立 JSON 存储（合并至 `remote_config_sync`）。

### Phase 2: 解耦与依赖治理 [P0]
- [ ] 彻底解决 **循环依赖**:
    - [ ] 重构 `core/container.py` 以支持 Provider 模式或 Setter 注入。
    - [ ] 将 `Settings.load_dynamic_config` 逻辑外迁至专门的初始化器。
- [ ] **核心链路解耦**:
    - [ ] 重构 `core/event_bus.py`: 打破循环依赖，移除对 `web_admin` 控制器的任何直接引用。

### Phase 3: 引导程序重构 (`main.py` 解耦) [P0]
- [ ] 创建 `core/bootstrap.py` 负责应用启动序列。
- [ ] 创建 `core/lifecycle.py` 负责统一的生命周期钩子（Startup/Cleanup）。
- [ ] 将 **Cron 逻辑** 从 `main.py` 移至专用的 `scheduler/cron_service.py`。

### Phase 4: 核心组件合并与服务化
- [ ] 将 `StateManager` 逻辑并入 `services/state_service.py`。
- [ ] 规范化 `ai/` 集成（提供者 -> 服务 -> 接口）。
- [ ] 统一数据库初始化和访问（`core/database.py` vs `db/`）。
- [ ] **基础设施池化 [P1]**: 在 `Container` 中初始化全局 `aiohttp.ClientSession` 连接池。
- [ ] **合并数据库管理器**: 清理 `utils/db/` 下冗余的 `database_manager.py` 与 `db_manager.py`。
