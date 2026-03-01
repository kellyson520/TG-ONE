# Report: Fix Event Optimization DB Locked Error

## Summary
Fixed the `sqlite3.OperationalError: database is locked` error originating from `core.helpers.event_optimization`. The error occurred during the `periodic_stats` background task due to a blocking synchronous database call holding an active read-write SQLite transaction (`BEGIN IMMEDIATE`). 

## Technical Details
- **Cause**: The `periodic_stats` function inside `EventDrivenMonitor` was periodically creating a synchronous database session using `core.db_factory.get_session()`. The default synchronous session automatically attempts to obtain a connection and initiates a transaction (`BEGIN IMMEDIATE` in global SQLite config), which will block if another worker process currently holds an active write lock. Because this also blocked the asyncio event loop, it severely harmed concurrency and led to timeout exceptions.
- **Solution**: 
    - Migrated the data fetch from `session.query(Chat.telegram_chat_id).filter(...)` to standard fully asynchronous SQLAlchemy 2.0 syntax using `select(...)` and `await session.execute(stmt)`.
    - Used the global `container.db.get_session(readonly=True)` to explicitly request a read-only async session. This bypasses the SQLite global write lock entirely, performing read operations without `BEGIN IMMEDIATE`.
- **Validation**:
    - Confirmed the code executes in the event loop asynchronously without triggering any potential transaction locks.
    - Code gracefully closes the connection using `async with` context managers.

## Status
Completed successfully. No further manual intervention is required.
