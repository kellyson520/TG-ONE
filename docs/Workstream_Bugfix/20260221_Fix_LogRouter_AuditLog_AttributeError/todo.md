# Fix LogRouter AuditLog AttributeError

## 背景 (Context)
在 `web_admin/routers/system/log_router.py` 的 `get_audit_logs` 函数中，尝试访问 `log.id` 时报错 `AttributeError: 'dict' object has no attribute 'id'`。
这表明 `log` 是一个字典对象，而不是一个具有 `id` 属性的模型对象。

## 待办清单 (Checklist)

### Phase 1: 问题诊断 (Diagnosis)
- [x] 读取 `web_admin/routers/system/log_router.py` 相关代码
- [x] 分析数据库查询返回的数据结构

### Phase 2: 核心修复 (Core Fix)
- [x] 修正 `get_audit_logs` 中的字段访问方式 (改为 `log['id']` 或使用模型转换)
- [x] 检查该函数中其他类似的字段访问是否存在同类问题

### Phase 3: 验证与清理 (Verify & Cleanup)
- [x] 验证修复后的接口返回
- [x] 更新 `report.md`
- [x] 更新 `docs/process.md` 状态
