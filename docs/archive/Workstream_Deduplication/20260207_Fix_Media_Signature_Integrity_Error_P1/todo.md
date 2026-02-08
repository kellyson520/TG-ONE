# 修复媒体签名唯一约束冲突问题 (Fix Media Signature Integrity Error)

## 背景 (Context)
在 `repositories/dedup_repo.py` 的 `batch_add_media_signatures` 方法中，存在尝试插入重复 `(chat_id, signature)` 的情况，导致 `sqlite3.IntegrityError: UNIQUE constraint failed`。这通常发生在并发插入或批处理中包含重复条目时。

## 待办清单 (Checklist)

### Phase 1: 问题诊断与重现
- [x] 分析 `repositories/dedup_repo.py` 中 `batch_add_media_signatures` 的实现。
- [x] 编写单元测试重现 `UNIQUE constraint failed` 错误。

### Phase 2: 核心修复
- [x] 方案一：在插入前在内存中对批处理数据进行去重。
- [x] 方案二：使用 `ON CONFLICT DO UPDATE` (upsert) 或 `DO NOTHING`。
- [x] 执行修复。

### Phase 3: 验证与验收
- [x] 运行单元测试确保修复有效。
- [x] 检查是否对系统性能有负面影响。
- [x] 更新 `report.md` 并更新 `docs/process.md`。
