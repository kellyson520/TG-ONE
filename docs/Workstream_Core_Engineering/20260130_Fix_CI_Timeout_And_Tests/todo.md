# Fix CI Timeout and Test Failures

## 背景 (Context)
GitHub CI 线上单元测试超时（耗时超过6小时），且存在多个测试失败和错误：
1. `cannot unpack non-iterable coroutine object` (Trace Middleware)
2. `object MagicMock can't be used in 'await' expression` (Conftest)
3. `CSRF token validation failed` (Auth Login)

## 待办清单 (Checklist)

### Phase 1: 诊断与复现
- [ ] 运行本地单元测试，定位导致超时的测试用例
- [ ] 收集详细日志，分析 `trace_middleware` 的 unpacked coroutine 错误
- [ ] 检查 `tests/conftest.py` 中的 Mock 设置

### Phase 2: 核心错误修复
- [ ] 修复 `trace_middleware.py`: 确保异步调用被正确 await
- [ ] 修复 `tests/conftest.py`: 将 `MagicMock` 替换为 `AsyncMock` 处理异步初始化
- [ ] 修复 CSRF 验证失败: 优化测试中的 Token 生成与验证逻辑

### Phase 3: 性能优化与超时治理
- [ ] 识别并修复测试中的挂起/死循环逻辑
- [ ] 优化数据库初始化，减少每个测试套件的开销
- [ ] 验证 CI 流水线性能，确保在合理时间内完成

### Phase 4: 验证与报告
- [ ] 运行 `local-ci` 确保所有检查通过
- [ ] 生成交付报告 `report.md`
- [ ] 更新 `docs/process.md`
