# 完善更新系统 (Enhance Update System)

## Context
当前 `update_service.py` 虽然修复了 HTTP 更新中的目录创建问题，但仍存在显著的架构缺陷，特别是在非 Git 环境下：
1.  **回滚机制缺失**: `rollback()` 方法强依赖 `git reset`。对于 HTTP 更新（无 Git 仓库）的用户，一旦更新失败或通过健康检查失败，**无法回滚**，会导致服务完全瘫痪。
2.  **文件占用风险**: Windows 环境下，直接覆盖正在运行的文件可能引发 `PermissionError`。
3.  **安全性不足**: HTTP 更新缺乏对下载文件的完整性校验（Hash Check）。

## Strategy
1.  **通用回滚层 (Universal Rollback)**:
    - 引入 `BackupManager`。
    - 在 HTTP 更新前，自动将 `src` (及其他核心目录) 压缩备份到 `data/backups/`.
    - 重写 `rollback()`：检测环境，若无 Git 则从最近的备份 Zip 还原。
2.  **原子写入优化 (Atomic Write)**:
    - 采用 "Write-to-Temp & Swap" 策略，或在 Windows 上使用重命名替换策略，减少文件锁定冲突。
3.  **健壮性增强**:
    - 增加文件操作的重试装饰器。

## Checklist

### Phase 1: Robust Backup & Rollback
- [x] Refactor `services/update_service.py` to support file-based backup.
- [x] Implement `_create_local_backup()` before HTTP update.
- [x] Implement `_restore_from_local_backup()` for rollback strategy.

### Phase 2: Windows Compatibility
- [x] Add retry logic for file overwrites(`shutil.copy` operations).
- [x] Ensure `__pycache__` and logs are strictly ignored during backup/restore.

### Phase 3: Verification
- [ ] Verify backup creation.
- [ ] Verify restore logic (Dry Run).
