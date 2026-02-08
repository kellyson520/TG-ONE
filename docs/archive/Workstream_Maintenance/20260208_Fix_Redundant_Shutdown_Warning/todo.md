# Todo: Fix Redundant Shutdown Warning

- [x] Identify redundant shutdown call paths (Signal handler, error handler, main loop end) <!-- id: 0 -->
- [x] Modify `core/lifecycle.py` to add `is_shutting_down` check <!-- id: 1 -->
- [x] Modify `core/shutdown.py` to lower log level for redundant calls from WARNING to INFO <!-- id: 2 -->
- [x] Modify `main.py` to remove redundant `stop()` call on startup failure <!-- id: 3 -->
- [x] Verify with reproduction script <!-- id: 4 -->
- [x] Report completion <!-- id: 5 -->
