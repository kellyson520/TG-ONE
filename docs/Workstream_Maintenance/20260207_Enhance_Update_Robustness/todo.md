# Task: Enhance Update Robustness and Cleanup

## Background
Based on `test_final.txt` and user requests, the `entrypoint.sh` needs to be more robust by moving dependency checks into the main loop. Additionally, we need to ensure that dependencies strictly align with `requirements.txt` (uninstalling extraneous ones) and limit the number of backups to prevent disk bloat.

## Objectives
1.  **Refactor `entrypoint.sh`**:
    *   Move `check_and_fix_dependencies` into the `while true` loop.
    *   Implement "Strict Dependency Alignment" (uninstall packages not in `requirements.txt`).
    *   Implement Backup Rotation (limit to 10 backups).
2.  **Enhance `UpdateService.py`**:
    *   Add backup rotation for database and code backups.
    *   Limit backups to a configurable number (default 10).

## TODO
- [x] Initialize Workstream Docs
- [x] Implement strict dependency check in Python helper script or logic
- [x] Update `scripts/ops/entrypoint.sh`
- [x] Update `services/update_service.py`
- [x] Verify changes (manual check of script logic)
- [x] Final Report
