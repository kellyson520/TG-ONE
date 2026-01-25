# Verification Report: Phase 2 Core Infrastructure Repair

## 1. 任务概览 (Task Executive Summary)
本阶段目标是针对 **Phase 2 (基础设施重构)** 进行质量验收、Bug 修复及垃圾代码的彻底清理。通过核心组件的单元测试扫描，发现并修复了多项隐蔽缺陷，确保了系统启动链路与生命周期的稳定性。

## 2. 核心修复清单 (Core Fixes)

### 2.1 架构合规性修复 [P0]
- **Bug**: `core/container.py` 在模块顶部直接实例化 `container = Container()`，违反了 `core-engineering` 的极致惰性执行标准，且由于其初始化涉及数据库引擎获取，增加了单元测试的脆弱性。
- **Fix**: 引入 `ContainerProxy` 与 `get_container()` 访问器，实现 **极致延迟加载**。全局变量 `container` 现在仅作为代理，直到属性被首次访问时才触发实例化。

### 2.2 启动序列可靠性增强 [P1]
- **Bug**: `core/bootstrap.py` 使用原生 `asyncio.create_task` 启动 Web 服务和心跳检测，若这些任务由于异常崩溃或配置错误失败，错误将被静默或难以回溯。
- **Fix**: 统一封装使用 `services.exception_handler.exception_handler.create_task`。现在所有后台任务均受到全局异常管理器的监控，并自动记录 TraceID。

### 2.3 物理目录彻底清理 [P0]
- **Issue**: `zhuanfaji/` 目录在大盘 todo 中标记为已删除，但实际物理存在，造成配置干扰。
- **Action**: 执行物理删除，确保工作空间整洁度符合 `workspace-hygiene` 规范。

### 2.4 测试套件回归修复 [P0]
- **Issues**:
    - `test_settings.py`: 由于 `conftest.py` 过度 Mock `core.config` 模块，导致无法测试真实的 `Settings` 逻辑。
    - `test_message_pipeline.py`: 由于 `Pipeline` 内部调用了 `get_display_name_async` 辅助函数（涉及数据库访问），且 `DedupMiddleware` 接口已变更，导致测试崩溃。
- **Fixes**:
    - 修正 `conftest.py` 的 Mock 逻辑，向 Mock 模块中注入真实的 `Settings` 类。
    - 在测试中 Patch `get_display_name_async` 路径，并对齐 `DedupService.check_and_lock` 接口规格。

## 3. 测试验证矩阵 (Verification Matrix)

| 模块 | 测试文件 | 状态 | 关键点 |
| :--- | :--- | :--- | :--- |
| **Container** | `test_container.py` | ✅ PASSED | 验证单例、Repo 注入、生命周期 |
| **EventBus** | `test_event_bus_isolated.py` | ✅ PASSED | 验证异步发布订阅、错误隔离 |
| **Pipeline** | `test_message_pipeline.py` | ✅ PASSED | 验证 Loader -> Dedup -> Sender 链路 |
| **Settings** | `test_settings.py` | ✅ PASSED | 验证 Pydantic v2 校验、Env 覆盖 |

## 4. 结论与遗留问题 (Conclusion & Next Steps)
Phase 2 的核心稳定性已得到验证。
- **遗留 P2**: `services/state_service.py` 逻辑仍较为单薄，暂未完全替代 `handlers/` 下的 `SessionManager` 状态持久化。建议在 Phase 3 模块细化阶段进一步打通。
- **架构建议**: 在后续 Phase 3 中，应强制将 `utils/db/db_operations.py` 中的逻辑根据功能下沉至各 `Repository`。

**Phase 2 重构已进入 "生产级稳定" 状态。**
