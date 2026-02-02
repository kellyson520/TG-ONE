# Fix Chat Model Attribute Error

## 背景 (Context)
系统在运行定期统计任务时报错 `type object 'Chat' has no attribute 'is_active'`。
经查，`models/chat.py` 中缺失 `is_active` 字段定义，但在 `core/helpers/event_optimization.py` 等多处代码中被使用，且 `models/migration.py` 中已有对应的数据库迁移逻辑。

## 待办清单 (Checklist)

### Phase 1: 修复模型定义
- [x] 在 `models/chat.py` 中添加 `is_active` 字段
- [x] 检查 `Chat` 模型中是否还缺失其他在 `migration.py` 中提到的字段

### Phase 2: 验证与同步
- [x] 运行数据库对齐检查
- [x] 验证 `event_optimization.py` 中的错误是否消失
- [x] 更新 `process.md`

### Phase 3: 归档
- [x] 提交报告并归档
