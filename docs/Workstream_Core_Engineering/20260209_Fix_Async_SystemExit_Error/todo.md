# Task: Fix Async SystemExit Error

## 📋 Todo List
- [x] Research root cause of `RuntimeError: Event loop is closed` on `sys.exit` in Telethon/uvloop <!-- id: 0 -->
- [x] Analyze `app/services/update_service.py` implementation of `trigger_update` <!-- id: 1 -->
- [x] Analyze `app/handlers/commands/system_commands.py` interaction with update service <!-- id: 2 -->
- [x] Implement a safer way to signal system exit/restart that allows the event loop to stop gracefully <!-- id: 3 -->
- [x] Verify fix by simulating update trigger <!-- id: 4 -->
- [x] Cleanup and archive <!-- id: 5 -->

## 📈 Progress
- 2026-02-09: Task initialized.
- 2026-02-09: Root cause identified (abrupt loop termination).
- 2026-02-09: Implemented `LifecycleManager` shutdown signaling and main loop wait logic.
- 2026-02-09: Verified via simulation script.
