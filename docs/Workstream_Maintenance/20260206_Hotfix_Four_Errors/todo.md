# 20260206_Hotfix_Four_Errors

## 背景 (Context)
解决日志中出现的四个核心错误：配置属性缺失 (Error 1)、MessageContext 属性缺失 (Error 3)、MockEvent 缺失 Client (Error 4) 以及 SQLAlchemy Greenlet 异步错误 (Error 2)。这些错误会导致系统在处理历史消息、媒体组及数据库操作时崩溃或行为异常。

## 待办清单 (Checklist)

### Phase 1: 基础属性与配置修复
- [x] 修复 Error 1: 在 `core/config/__init__.py` 中添加 `HISTORY_MESSAGE_LIMIT` 字段
- [x] 修复 Error 3: 在 `filters/context.py` 的 `MessageContext` 中添加 `media_blocked` 属性及初始化

### Phase 2: 逻辑安全加固
- [x] 修复 Error 4: 在 `filters/init_filter.py` 中为 `event.client` 访问添加 `getattr` 安全检查
- [x] 验证 `handlers/button/modules/history.py` 是否安全使用了 `HISTORY_MESSAGE_LIMIT`

### Phase 3: 数据库异步合规性
- [x] 修复 Error 2: 在 `core/database.py` 中将 `expire_on_commit` 设为 `False`
- [x] 确保 `core/helpers/history/error_handler.py` 中的数据库回滚操作已 `await`

### Phase 4: 验证与验收
- [ ] 运行核心功能验证
- [ ] 更新 `docs/process.md` 状态
- [ ] 提交任务报告 `report.md`
