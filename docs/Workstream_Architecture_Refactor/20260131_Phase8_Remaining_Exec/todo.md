# Phase 8 剩余项执行 (Remaining Phase 8 Execution)

## Context
执行 Phase 8 剩余的三项核心任务：性能门禁、智能休眠、架构图更新。
Parent: [Process](../process.md)

## Checklist

### 1. 性能门禁库集成 (Performance Gatekeeper)
- [x] **创建/集成 Gatekeeper 库**: 实现资源检查逻辑 (RAM < 2GB 等约束)。(Ref: `core-engineering`)
- [x] **集成到 Startup/Runtime**: 在关键节点添加检查钩子。
- [x] **验证测试**: 确保不会误杀正常进程，且无 Stress Test。

### 2. 智能休眠方案 (Smart Sleep Scheme)
- [x] **设计 Sleep 策略**: 定义 Idle 状态与唤醒机制。 
- [x] **实现 SleepManager**: 实现休眠逻辑 (e.g. reduce polling rate, close connections if idle).
- [x] **集成到 Main Loop**: 在主循环/调度器中调用。

### 3. 架构图更新 (Architecture Diagram Update)
- [x] **更新 `docs/tree.md`**: 确保文件树最新。
- [x] **更新/创建 Architecture Diagram**: 生成 Mermaid 或文本描述的架构图，反映最新重构状态 (Settings SSOT, New Handlers, etc.)。
- [x] **更新 `Standard_Whitepaper.md`**: 如果有架构变更，同步更新白皮书。
