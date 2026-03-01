# Fix Event Optimization DB Locked Error

## Context
The `periodic_stats` task in `core/helpers/event_optimization.py` periodically fetches active chats from the database. It currently uses a synchronous database session `get_session()`, which blocks the event loop and defaults to a read-write transaction (`BEGIN IMMEDIATE` in recent SQLite configurations). This leads to `sqlite3.OperationalError: database is locked` errors during high concurrency.

## Strategy
1. **Migration to Async DB API**: Change the blocking `session.query()` to an async `session.execute(select(...))` call.
2. **Read-only Transaction**: Use `container.db.get_session(readonly=True)` to prevent the database connection from acquiring a write lock (`BEGIN IMMEDIATE`), avoiding transaction conflicts with the main worker processes.

## Phased Checklist

### Phase 1: Investigation & Planning
- [x] Locate the source of the `database is locked` error (`core/helpers/event_optimization.py`).
- [x] Formulate replacement utilizing `container.db.get_session(readonly=True)` and `select()`.

### Phase 2: Implementation
- [x] Refactor `periodic_stats` to use async `sqlalchemy.select` syntax.
- [x] Replace synchronous `core.db_factory.get_session` with `core.container.container.db.get_session(readonly=True)`.

### Phase 3: Verification
- [x] Document the changes in `report.md`.
- [x] Apply to `process.md`.
