# Task Report: Update System Robustness & Dependency Alignment

## 1. Summary
This task enhanced the reliability of the system update and guardian process. We implemented a more aggressive dependency check that occurs before every process restart, ensured that the environment strictly matches `requirements.txt` by uninstalling extraneous packages, and implemented a backup rotation policy to prevent disk space exhaustion.

## 2. Changes

### 2.1 entrypoint.sh (v3.0)
- **Process-Level Guard**: Moved `check_and_fix_dependencies` into the main `while` loop.
- **Strict Dependency Alignment**: Integrated a Python script to compare installed packages against `requirements.txt` and automatically uninstall packages not in the manifest.
- **Backup Rotation**: Added `prune_backups` to keep only the latest 10 code backups (`.tar.gz`).
- **Robustness**: Improved signal handling and reboot logic.

### 2.2 core/config/__init__.py
- Added `UPDATE_BACKUP_LIMIT` setting (default = 10).

### 2.3 services/update_service.py
- **Library Enhancement**: Added `_rotate_backups` method to handle both DB backups and Code backups.
- **DB Rotation**: Called rotation after varje DB backup in `trigger_update`.
- **Code Rotation**: Called rotation after varje local code backup (Zip) in `_create_local_backup`.

## 3. Verification Result
- **Infrastructure Check**: Cleaned up the `entrypoint.sh` logic to ensure it handles common edge cases (like git fetch failure) gracefully by rolling back.
- **Strict Sync**: Verified the Python parsing logic for `requirements.txt` handles common formats (pins, ranges, extras, markers).
- **Cleanup**: Verified that backup limit logic correctly identifies and removes older files based on modification time.

## 4. Maintenance Notes
- Backup files are stored in `data/backups/auto_update`.
- The `protected` list in `entrypoint.sh` prevents accidental uninstallation of critical infrastructure like `pip`, `setuptools`, `wheel`.
