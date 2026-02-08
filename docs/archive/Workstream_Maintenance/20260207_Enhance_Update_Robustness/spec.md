# Specification: Enhanced Update Robustness

## 1. entrypoint.sh Refactoring

### 1.1 Process-Level Dependency Guard
The dependency check will be moved into the main loop of `entrypoint.sh`. This ensures that if the Python process crashes due to a missing dependency (manually added to `requirements.txt`), the guardian will fix it before the next restart Attempt.

### 1.2 Strict Dependency Alignment
We will implementation a mechanism to:
1.  Read `requirements.txt`.
2.  Get list of currently installed packages using `pip list`.
3.  Identify packages that are NOT in `requirements.txt` (excluding standard/critical ones).
4.  Uninstall those extraneous packages.

### 1.3 Shell-Level Backup Rotation
In `perform_update` function:
- Keep the last 10 `.tar.gz` backups.
- Remove older ones using `ls -t | tail -n +11 | xargs rm`.

## 2. UpdateService.py Enhancements

### 2.1 Python-Level Backup Rotation
Add `_rotate_backups(self, directory: Path, pattern: str, limit: int)` method.
- This will be used for both DB backups and Code backups.
- Default limit should be configurable via `settings`.

## 3. Technology
- Bash scripting
- Python `subprocess`
- `pip` CLI
