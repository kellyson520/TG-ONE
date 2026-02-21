# Audit Log Attribute Error Fix Report

## 摘要 (Summary)
修复了 `web_admin/routers/system/log_router.py` 中 `get_audit_logs` 接口在处理审计日志时发生的 `AttributeError: 'dict' object has no attribute 'id'` 错误。

## 架构变更 (Architecture Refactor)
无架构变更。仅修正了数据序列化时的字段访问方式。
由于 `AuditService.get_logs` 内部使用了 `UnifiedQueryBridge` 进行跨库联邦查询，返回的数据结构为字典列表 (`List[dict]`)，而原代码错误地尝试通过属性访问方式 (`log.id`) 获取字段。

## 验证结果 (Verification)
- [x] 编写并运行 `tests/verify_log_fix.py`，模拟 DuckDB 返回的字典数据，验证序列化逻辑正确性。
- [x] 验证包含：
    - 字典字段访问 (`log.get("id")`)。
    - 时间戳转换逻辑 (`datetime` 对象转 ISO 字符串，或字符串透传)。
    - 空值处理。

## 修复细节 (Fix Details)
修改前：
```python
"id": log.id,
"timestamp": log.timestamp.replace(tzinfo=timezone.utc).isoformat()
```

修改后：
```python
"id": log.get("id"),
"timestamp": ts_str # 增加了对 datetime 或 string 类型的安全检查
```
