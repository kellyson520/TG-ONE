# Task: Fix Redundant Shutdown Warning

## Context
The user reported a warning: `关闭流程已在进行中，忽略重复调用` appearing during shutdown. This is caused by multiple code paths triggering the system shutdown (e.g., signal handlers, main loop completion, and error handlers).

## Objectives
- [ ] Investigate and identify all redundant shutdown call paths.
- [ ] Make `LifecycleManager.stop()` idempotent and silent if already stopping.
- [ ] (Optional) Adjust `ShutdownCoordinator.shutdown()` log level for repeated calls if appropriate.

## Approach
1. Modify `core/lifecycle.py`:
   - In `stop()`, check if the coordinator is already shutting down before proceeding.
2. Review `main.py`:
   - Ensure exceptions in `start()` don't cause double `stop()` calls if `LifecycleManager` already handles it.
3. Verify with a reproduction script.
