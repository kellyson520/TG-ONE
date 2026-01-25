# Optimization Tasks

## P0: Immediate Actions (High Impact, Low Effort)
- [ ] **Dependency Update**: Add `uvloop` and `orjson` to `requirements.txt`.
- [ ] **Config Tuning**: Enable SQLite WAL mode in `core/database.py` or equivalent.
- [ ] **Memory**: Add `__slots__` to `MessageContext` and other high-frequency classes.

## P1: Short Term (Medium Impact, Medium Effort)
- [ ] **Batching**: Implement `LogBatcher` to buffer logs before writing to DB.
- [ ] **Frontend**: Implement Vue Router lazy loading for non-critical pages.
- [ ] **Frontend**: Switch real-time logs to WebSocket (if not already fully done).

## P2: Long Term (High Stability)
- [ ] **Archiving**: Create a daily cron job to move old logs to Parquet files.
- [ ] **Deduplication**: Implement Bloom Filter middleware.
- [ ] **Circuit Breaker**: Implement `TelegramCircuitBreaker` class.
