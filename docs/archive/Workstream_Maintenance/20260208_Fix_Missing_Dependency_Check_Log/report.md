# Report: Fix Missing Dependency Check Log

## Summary
The user reported that the log did not output dependency check progress after a `/update` restart. Investigation revealed that the `check_and_fix_dependencies` function in `scripts/ops/entrypoint.sh` was silent when the check was successful. This led to a gap in the logs between the guardian start and the application start.

## Changes
- Modified `scripts/ops/entrypoint.sh`:
    - Added `echo "🔍 [守护进程] 正在校验 Python 依赖环境..."` before starting the check.
    - Added `echo "✅ [守护进程] 依赖环境校验通过。"` after a successful check.

## Verification
- Verified that `entrypoint.sh` logic now explicitly prints status messages for dependency verification.
- Verified that these messages will appear in the log redirected from `stdout`.

## Impact
- Users will now see clear confirmation of dependency checks during both initial startup and restarts after updates.
