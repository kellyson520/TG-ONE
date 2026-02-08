# Report: Fix Redundant Shutdown Warning

## Summary
The user reported a warning message `关闭流程已在进行中，忽略重复调用` appearing during system shutdown. This was caused by multiple triggers (Signal Handlers, Error Handlers, and Main Loop termination) calling the shutdown sequence simultaneously or sequentially.

## Changes
- **`core/lifecycle.py`**: Added a check in `LifecycleManager.stop()` to detect if the shutdown coordinator is already active. This prevents redundant calls from the high-level manager and keeps logs clean using `DEBUG` level.
- **`core/shutdown.py`**: Lowered the log level for redundant shutdown attempts within the `ShutdownCoordinator` from `WARNING` to `INFO`. Improved the message to be more descriptive: `系统关闭流程已由其他任务触发，忽略此次重复调用。`.
- **`main.py`**: Removed a redundant `lifecycle.stop()` call in the startup exception block, as `lifecycle.start()` already handles its own cleanup upon critical failure.

## Verification
- Created a reproduction script that triggered `lifecycle.stop()` twice.
- Confirmed that the first call executes the shutdown and the second call is silently ignored by `LifecycleManager`.
- Confirmed that the `WARNING` is no longer emitted under normal redundant scenarios.

## Impact
- System logs are now cleaner during shutdown and startup failures.
- Prevents confusing "Warning" messages for expected concurrent shutdown triggers.
