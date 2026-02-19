# 修复归档逻辑与路径清理 - 任务清单

**项目**: TG ONE 归档与清理系统修复
**负责人**: Antigravity
**优先级**: 🔴 高
**状态**: ✅ 已完成

---

## 📋 任务背景
1. **移除旧的任务队列清理逻辑**: 由于已实现冷热分层（归档至 Parquet），原有的直接在 SQLite 中基于时间的物理删除逻辑已过时，且可能导致数据在归档前被误删。
2. **统一路径规范**: 修复可能存在的 `/achive` (拼写错误) 或错误的根目录 `/archive` 引用，确保所有数据均位于 `data/` 目录下。

---

## 📅 任务阶段

### Phase 1: 代码审计与清理 (Cleanup) ✅
- [x] 审计 `core/db_factory.py` 中的 `async_cleanup_old_logs` 和 `cleanup_old_logs`。
- [x] 移除对 `TaskQueue` 的硬删除逻辑（已从 `async_cleanup_old_logs` 中移除直接删除 TaskQueue 的代码段）。
  - `cleanup_old_logs` 为同步包装器，委托给 `async_cleanup_old_logs`，自动生效。
- [x] 检查 `services/system_service.py` 中的清理调用 → `DBMaintenanceService.auto_archive_data` 正确委托给各 Repository 的归档方法。
- [x] 检查 `scripts/ops/manage_db.py` 中的清理指令 → 无额外硬删除逻辑。
- [x] 检查 `web_admin/routers/system/stats_router.py` → 仅有管理员手动删除单个任务的 API（by task_id），属于正常管理操作，保留。

### Phase 2: 路径一致性检查 (Path Refactor) ✅
- [x] 深度扫描所有配置文件和脚本，寻找 `/achive` 或错误的绝对路径 `/archive` → **未发现任何活跃代码包含拼写错误**。
- [x] 确保 `ForwardRecorder` 的存储路径符合 `data/zhuanfaji` 规范 → 使用 `settings.FORWARD_RECORDER_DIR`，正确指向 `data/zhuanfaji`。
- [x] 验证 `ArchiveManager` 和 `ArchiveStore` 的根路径设置 → 均从 `settings.ARCHIVE_ROOT` 读取，默认为 `data/archive/parquet`（绝对路径）。
- [x] 验证 Dockerfile → 不包含错误路径；`data/archive` 由 `archive_init.py` 的 `init_archive_system()` 动态创建。
- [x] 验证 `docker-compose.yml` → `ARCHIVE_ROOT=/app/data/archive/parquet`, `BLOOM_ROOT=/app/data/archive/bloom`，正确。
- [x] 验证 `entrypoint.sh` → 无归档路径引用，归档目录创建由 Python 层负责。

### Phase 3: 归档逻辑增强 (Archive Enhancement) ✅
- [x] 确认 `UniversalArchiver.archive_table()` 在归档成功后负责 SQLite 记录的清理 → 在 `engine.py` 第 125-132 行，写入 Parquet 后分批删除已归档的 ID。
- [x] 确认 `ArchiveManager.archive_model_data()` 同样包含"写入 Parquet → 删除主库记录"的闭环逻辑。
- [x] 验证 `HOT_DAYS_LOG`, `HOT_DAYS_TASK`, `HOT_DAYS_STATS`, `HOT_DAYS_SIGN` 等参数 SSOT 为 `core/config/__init__.py`。

### Phase 4: 验证与报告 (Verify) ✅
- [x] 代码变更已完成且通过审查。
- [x] 提交报告。

---

## 📝 变更摘要

### 修改的文件
| 文件 | 修改内容 |
|------|----------|
| `core/db_factory.py` | 移除 `async_cleanup_old_logs` 中 TaskQueue 的直接删除逻辑（约 16 行），改为注释说明由 UniversalArchiver 处理。更新了统计记录逻辑。 |

### 验证结论
- **路径一致性**: 项目中所有归档相关路径均正确指向 `data/archive/` 子目录，无 `/achive` 拼写错误。
- **数据安全**: TaskQueue 数据不再被定时日志清理直接删除，而是由归档流程（`UniversalArchiver` / `ArchiveManager`）先写入 Parquet 冷存储，再从 SQLite 中清理。
- **SSOT**: 所有天数阈值和路径配置均从 `core.config.settings` 统一读取。
