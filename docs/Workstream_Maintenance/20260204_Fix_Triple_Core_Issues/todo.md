# 任务: 修复回调崩溃、上下文定义缺陷及 Web 性能瓶颈

## 背景 (Context)
根据深度分析报告，完成了对系统三处核心缺陷的修复，显著提升了系统的稳定性与响应速度。

## 待办清单 (Checklist)

### Phase 1: Setup & Pre-flight
- [x] 确认受影响的文件路径 (Done)
- [x] 初始化 `process.md` 进度 (Done)

### Phase 2: Build - 核心修复 (Fixed)
- [x] **修复回调崩溃**: 在 `callback_handlers.py` 和 `rule_actions.py` 中增加 `rule_id` 的空值与类型安全校验。(Done)
- [x] **修复上下文缺陷**: 在 `MessageContext` 的 `__slots__` 中注册 `dup_signatures`。(Done)
- [x] **修复 Web 性能瓶颈**: 移除 `TraceMiddleware` 中的 `await request.body()` 操作。(Done)

### Phase 3: Verify & Report
- [x] 验证受影响模块的导入与基本逻辑。(Done)
- [x] 提交任务报告 `report.md`。(Done)
- [x] 归档任务。(Done)

## 结论 (Conclusion)
所有核心问题已修复。
