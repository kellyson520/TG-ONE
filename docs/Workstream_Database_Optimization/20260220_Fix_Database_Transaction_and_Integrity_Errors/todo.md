# 修复数据库事务与完整性错误 (Fix Database Transaction and Integrity Errors)

## 背景 (Context)
用户报告了两个核心数据库错误：
1. `VACUUM` 失败：由于在事务内部执行导致。
2. `media_signatures` 唯一约束失败：在插入媒体签名时发生冲突。

## 待办清单 (Checklist)

### Phase 1: 问题诊断 (Diagnosis)
- [x] 搜索 `VACUUM` 调用点并分析其事务上下文
- [x] 定位 `media_signatures` 插入逻辑并分析并发/重复处理流程
- [x] 复现或确认错误发生路径

### Phase 2: 修复 VACUUM 错误
- [x] 确保 `VACUUM` 在独立连接且无活动事务的情况下运行
- [x] 优化数据库维护脚本的执行逻辑

### Phase 3: 修复唯一约束冲突
- [x] 实现 `media_signatures` 的 Upsert 逻辑 (ON CONFLICT DO UPDATE) -> 通过 GroupCommit 弹性 Fallback 实现
- [x] 增强媒体处理的并发安全性

### Phase 4: 验证与报告
- [x] 运行相关集成测试
- [x] 生成交付报告 `report.md`
- [x] 更新 `process.md`
