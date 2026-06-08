# Task: Fix SQLite Disk I/O Error

## Status
- [x] Analyze the root cause of `sqlite3.OperationalError: disk I/O error`
- [x] Review `fetch_next` implementation in `TaskRepository`
- [x] Optimize `fetch_next` to split complex UPDATE into SELECT+UPDATE
- [x] Verify fix with tests (Extended concurrency & edge case tests)
- [x] Implement automatic cleanup mechanism for Cloud VPS (`bootstrap.py`)
