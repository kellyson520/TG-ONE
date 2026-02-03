# 全面现代化组件调用 (Modernize Calls)

## 背景 (Context)
随着重构的进行，系统中存在多种访问数据库会话和核心组件的方式（如 `async_db_session`, `AsyncSessionManager`, `container.db_session` 等）。
为了保持代码整洁和架构统一，需逐步移除老旧属性和别名，全面使用 `container.db.session()` 及其他标准 Container 属性。

## 策略 (Strategy)
1. **统一 DB Session**: 将所有 `container.db_session()`, `async_db_session()`, `AsyncSessionManager()` 替换为 `container.db.session()`。
2. **清理别名**: 移除 `core/container.py` 中的 `db_session` 兼容性属性。
3. **清理旧模块**: 若 `repositories/db_context.py` 不再被使用，则将其标记为遗留或移除。
4. **统一组件访问**: 确保所有服务和处理器通过 `container` 单例访问依赖。

## 待办清单 (Checklist)

### Phase 1: 统一 container.db.session()
- [ ] 替换 `handlers/` 下的 `container.db_session()` -> `container.db.session()`
- [ ] 替换 `tests/` 下的 `container.db_session()` -> `container.db.session()`
- [ ] 替换 `services/` 下的 `container.db_session()` -> `container.db.session()`

### Phase 2: 移除 async_db_sessionHelper
- [ ] 扫描并替换 `async_db_session()` (来自 `repositories.db_context`)
- [ ] 更新相关文件的 import 语句
- [ ] 验证功能正常

### Phase 3: 清理与归档
- [ ] 移除 `core/container.py` 中的 `db_session` property
- [ ] 审计 `repositories/db_context.py` 的剩余用途
- [ ] 审计 `core/db_factory.py` 的 `AsyncSessionManager` 用途

### Phase 4: 验证
- [ ] 运行核心测试
- [ ] 运行集成测试
