# 修复缓存数据库损坏 (Fix Cache Database Corruption)

## Context
用户报告 `core.cache.unified_cache` 出现 `database disk image is malformed` 错误。这表明 SQLite 缓存数据库 (`db/cache.db`) 已损坏。虽然之前尝试过手动删除，但似乎需要更自动化的恢复机制。

## Strategy
1.  **自动检测与恢复**: 在 `SQLitePersistentCache` 中捕获 `sqlite3.DatabaseError`。
2.  **自愈逻辑**: 当捕获到 malformed 错误时，自动关闭连接，删除损坏的数据库文件，并重新初始化。
3.  **Bootstrap 增强**: 在系统启动的 `DatabaseHealthChecker` 中增加对 `cache.db` 的检查（目前可能只检查了主库 `forward.db`）。

## Checklist

### Phase 1: Robust Persistent Cache
- [x] 分析 `core/cache/persistent_cache.py`
- [x] 在 `get/set` 等核心方法中增加 `try-except sqlite3.DatabaseError` 块
- [x] 实现 `_handle_corruption` 方法：关闭连接 -> 删除文件 -> 重建

### Phase 2: Startup Check
- [x] 检查 `scripts/ops/database_health_check.py` 是否包含对 cache db 的检查
- [x] 如果没有，利用 `db_maintenance_service` 增强启动时的清理

### Phase 3: Verification
- [ ] 模拟损坏（写入垃圾数据到 `db/cache.db`）
- [ ] 运行应用，验证是否自动恢复且不崩溃
