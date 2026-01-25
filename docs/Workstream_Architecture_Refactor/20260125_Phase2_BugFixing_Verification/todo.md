# Phase 2 Bug Fixing & Verification

## 背景 (Context)
Phase 2 (基础设施重构) 已初步完成，但可能引入了回归或新 Bug。需要通过单元测试进行全面扫描、修复并验证核心链路的稳定性。重点关注 Container, EventBus, Bootstrap 和 Lifecycle 模块。

## 待办清单 (Checklist)

### Phase 1: 质量探测与架构审计
- [x] 运行 `tests/unit/core/test_container.py` [P0]
- [x] 运行 `tests/unit/core/test_event_bus_isolated.py` [P0]
- [x] 运行 `tests/unit/core/test_message_pipeline.py` 并修复 Bug [P0]
- [x] 验证 `main.py` -> `bootstrap.py` 的迁移是否完整，无导入异常 [P0]

### Phase 2: Bug 修复与重构完善
- [x] 修复 Container 的 Module-level Singleton 问题，改为 Lazy Proxy [P1]
- [x] 增强 Bootstrap 中的背景任务错误捕获 [P1]
- [x] 彻底删除 `zhuanfaji` 冗余目录 [P1]
- [x] 修复 `test_settings.py` 与 `test_message_pipeline.py` 的回归错误 [P0]

### Phase 3: 最终验证与报告
- [ ] 核心链路单元测试全量通过 [P0]
- [ ] 运行 `scripts/check_architecture.py` 进行架构合规性扫描 [P1]
- [ ] 生成 `report.md` [P0]
