# Report: SQLite Disk I/O Error Fix (2026-02-14)

## Summary
Resolved critical SQLite `disk I/O error` encountered during high-concurrency task fetching operations. The issue was traced to a complex atomic `UPDATE ... FROM SELECT` query in `TaskRepository.fetch_next` which caused locking contention and I/O timeouts under load. The query was refactored into a two-step `SELECT` then `UPDATE by ID` pattern, which significantly reduces lock duration and complexity.

## Key Changes
1.  **Optimized `fetch_next` Query Strategy**:
    - Replaced the single complex UPDATE statement (prone to I/O errors) with a split Read-Modify-Write approach.
    - Added explicit retry logic for `OperationalError` (DB locked / I/O error) with exponential backoff.
    - Improved group fetching logic to correctly include `running` (expired lock) tasks, ensuring no task is left behind during group processing.

2.  **Verified WAL Mode**:
    - Confirmed database is running in `WAL` (Write-Ahead Logging) mode, which is essential for concurrency.

3.  **Extended Testing**:
    - Added `tests/unit/repositories/test_task_repo_extended.py` to simulate concurrency and verify edge cases (mixed status groups).
    - Verified fix passes existing unit tests.

## Root Cause Analysis
The original `fetch_next` implementation used a subquery-heavy UPDATE statement:
```sql
UPDATE task_queue SET status=?, ... WHERE task_queue.id IN (SELECT ... LIMIT ?) OR ...
```
In SQLite, executing a complex SELECT inside an UPDATE on the same table can lead to extensive locking, especially when combined with offset/limit and multiple conditions. This often manifests as `disk I/O error` when the journal commit takes too long or conflicts with other readers.

## Resolution
The query was split:
1.  **SELECT Phase**: Fetch candidate IDs and their group IDs using standard SELECT queries (non-blocking for WAL readers).
2.  **UPDATE Phase**: Update the rows by direct ID list `WHERE id IN (...)`. This is extremely fast and minimizes the write lock window.
3.  **Retry Mechanism**: Added robust handling for transient SQLite errors to prevent worker crashes.

## Verification
- `pytest tests/unit/repositories/test_task_repo.py`: **PASSED**
- `pytest tests/unit/repositories/test_task_repo_extended.py`: **PASSED**
