# Fix Container Attribute Error (db_session)

## 背景 (Context)
系统在处理回调（如删除规则、修改规则设置）时抛出 `AttributeError: 'Container' object has no attribute 'db_session'`。
经查，`Container` 类确实没有 `db_session` 属性，而代码中大量使用了 `container.db_session()`。
预期应该是 `container.db.session()` 的别名。

## 待办清单 (Checklist)

### Phase 1: 核心修复
- [x] 在 `core/container.py` 中为 `Container` 类添加 `db_session` 别名属性/方法。
- [x] 或者：全局搜索并替换 `container.db_session()` 为 `container.db.session()`。（选择了添加别名，更稳健）
- [x] 验证 `handlers/button/callback/modules/rule_actions.py` 是否恢复正常。
- [x] 验证 `handlers/button/callback/modules/rule_settings.py` 是否恢复正常。

### Phase 2: 代码扫描与规范
- [x] 扫描全项目，查找是否有其他地方误用了 `db_session`。（已通过 grep 确认多处使用，均已因别名添加而恢复）
- [x] 确保架构符合 `architecture-auditor` 规范。
