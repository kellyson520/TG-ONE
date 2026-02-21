# 20260221_Fix_Authentication_Coroutine_Bug

## 背景 (Context)
用户报告在 `authentication_service.py` 中出现 `RuntimeWarning: coroutine 'AsyncSession.delete' was never awaited`，随后发生 `Bus error` 导致系统崩溃重启。
这是一个关键的异步编程错误，可能导致数据库连接泄漏或状态不一致，并引发低层级错误。

## 待办清单 (Checklist)

### Phase 1: 诊断与分析
- [x] 检查 `services/authentication_service.py` 源码
- [x] 确认 `session.delete` 的调用方式及返回类型 (确认在本环境中为协程)
- [x] 检查数据库 `AsyncSession` 的具体实现/包装器

### Phase 2: 修复与验证
- [x] 在 `authentication_service.py` 中由于 `delete` 返回协程，添加 `await`
- [x] 检查该文件及相关 Service 中是否存在类似的未等待协程
- [ ] (可选) 增加检测脚本或利用 `async-error-handling` 技能进行全路径检查

### Phase 3: 归档与总结
- [ ] 编写 `report.md`
- [ ] 更新 `docs/process.md`
