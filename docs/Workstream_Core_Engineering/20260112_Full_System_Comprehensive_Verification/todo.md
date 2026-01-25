# 全量系统综合验证计划

## 任务背景
在完成 Phase C, D, H 以及 Bot 指令优化后，需要进行一次全项目功能的联合测试，确保系统各模块协同正常，无回归问题。

## 任务清单 (Todo)
- [ ] **Phase 1: 自动化测试基线**
    - [x] 成功执行 `pytest --collect-only` (修复了 `test_rules_api.py` 的导入错误)
    - [ ] 运行全量 `pytest` 自动化测试 (进行中)
    - [ ] 分析测试失败项并分类修复
- [ ] **Phase 2: 关键链路人工串联 (逻辑检查)**
    - [ ] 验证消息转发完整流程 (Listener -> Pipeline -> Filter -> Sender)
    - [ ] 验证通知系统联动 (Error -> EventBus -> NotificationService -> Admin Bot)
    - [ ] 验证数据库运维指令链路 (/db_optimize, /db_backup)
- [ ] **Phase 3: 架构规范与完整性检查**
    - [ ] 检查所有 Handler 是否均通过 Service 层操作数据库
    - [ ] 检查 Container 生命周期管理是否覆盖所有新服务 (Notification, StatsFlush)
    - [x] 检查 `docs/tree.md` 是否同步最新文件系统
- [ ] **Phase 4: 性能与稳定性验证**
    - [ ] 检查 Stats Repository 的缓冲刷盘逻辑
    - [ ] 检查 GuardService 的内存与配置监控
- [ ] **Phase 5: 最终总结与报告**
    - [ ] 生成全量测试报告 `report.md`
    - [x] 更新全局进度 `docs/process.md`

## 验收标准
- 所有测试用例 Pass
- 无破坏分层架构的 Cross-layer 调用
- 系统日志中无未捕获的严重异常
