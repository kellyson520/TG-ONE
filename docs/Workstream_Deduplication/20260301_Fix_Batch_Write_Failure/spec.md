# Technical Specification: Fix Batch Write Failure

## Background
The `SmartDeduplicator` in `services/dedup/engine.py` uses a write buffer to batch insert media signatures. 
The actual insertion is handled by `DedupRepository.batch_add_media_signatures` in `repositories/dedup_repo.py`.
The current implementation uses `sqlite_insert().on_conflict_do_update()`.
A failure `INS` (likely `IntegrityError`) is occurring.

## Analysis of Potential Causes
1. **Duplicate (chat_id, signature) in same batch**: Handled by memory merge.
2. **Duplicate (chat_id, signature) with DB records**: Handled by `on_conflict_do_update`.
3. **Primary Key `id` conflict**: If `id` is somehow included in the records, it could cause conflicts.
4. **Data type mismatch**: e.g., `None` in a non-nullable field like `chat_id` or `signature`.
5. **SQL syntax error**: If `final_records` is empty or has some weird keys.
6. **SQLite multi-threading issues**: If two batches try to insert the same new record simultaneously.

## Proposed Strategy
1. **Enhanced Logging**: Change `logger.error(f"批量插入媒体签名失败: {e}", exc_info=True)` to also include some sample records from the batch.
2. **Strict Data Sanitization**:
    - Ensure `chat_id` and `signature` are NOT NULL.
    - Ensure `count` is positive.
    - Ensure `file_id` is a string.
3. **Handle Recursive Insertion**: If a batch fails, try inserting records one by one to isolate the problematic record (or at least log it).

## Expected Outcome
1. Persistence of deduplication data is stable.
2. Error logs are more informative.
3. No re-queuing of records unless there's an actual DB failure.
