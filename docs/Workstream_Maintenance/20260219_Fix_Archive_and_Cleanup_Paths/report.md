# 修复归档逻辑与路径清理 - 完成报告

**任务**: Fix Archive and Cleanup Paths
**日期**: 2026-02-19
**状态**: ✅ 已完成

---

## 🎯 目标

1. 移除 `core/db_factory.py` 中过时的 TaskQueue 直接硬删除逻辑，防止数据在冷存储归档前被误删。
2. 全面审计项目中所有归档相关路径引用，确保一致性和正确性。

---

## 📊 质量矩阵

| 指标 | 结果 |
|------|------|
| 代码修改量 | 1 文件, 净减少 ~16 行 |
| 路径一致性 | ✅ 所有路径正确 |
| `/achive` 拼写错误 | ✅ 未发现 |
| SSOT 合规 | ✅ 配置统一从 settings 读取 |
| 数据安全风险 | ✅ 消除（归档前不再直接删除） |
| 架构影响 | 无，仅移除冗余逻辑 |

---

## 🔧 变更详情

### `core/db_factory.py` - `async_cleanup_old_logs()`

**Before**: 函数在清理 RuleLog / ErrorLog / AuditLog 的同时，会直接删除 `status IN ('completed', 'failed')` 且 `updated_at < cutoff` 的 TaskQueue 记录。

**After**: 移除了 TaskQueue 的直接删除逻辑。该职责现由以下两个组件承担：
- `UniversalArchiver.archive_table()` — 先写入 Parquet，再批量删除源记录
- `ArchiveManager.archive_model_data()` — 同样的"归档→删除"闭环

统计记录逻辑已更新，`tasks_removed` 参数固定为 `0`，因为任务清理数量现在由归档流程自行统计。

---

## 🔍 路径审计结果

| 组件 | 路径配置 | 来源 | 状态 |
|------|----------|------|------|
| ARCHIVE_ROOT | `data/archive/parquet` | `.env` / `settings` | ✅ |
| BLOOM_ROOT | `data/archive/bloom` | `.env` / `settings` | ✅ |
| FORWARD_RECORDER_DIR | `data/zhuanfaji` | `.env` / `settings` | ✅ |
| Docker ARCHIVE_ROOT | `/app/data/archive/parquet` | `docker-compose.yml` | ✅ |
| Docker BLOOM_ROOT | `/app/data/archive/bloom` | `docker-compose.yml` | ✅ |
| archive_init 目录创建 | 动态创建于 ARCHIVE_ROOT | `archive_init.py` | ✅ |

---

## 📝 结论

项目的归档路径配置完全一致且正确。唯一的代码变更是移除了 `async_cleanup_old_logs` 中的冗余 TaskQueue 删除逻辑，确保数据不会在归档前被意外清理。该变更风险极低，因为：

1. TaskQueue 的清理职责已由 `UniversalArchiver` 接管
2. `DBMaintenanceService.auto_archive_data()` 方法正确调度所有表的归档
3. `AUTO_ARCHIVE_ENABLED` 配置默认开启
