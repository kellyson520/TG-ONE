# Fix Deduplication Engine Batch Write Failure

## Context
Deduplication engine is failing to batch write media signatures to the database. 
Log shows: `[ERROR][repositories.dedup_repo] 批量插入媒体签名失败: INS`.
This prevents persistence of deduplication data and causes re-queuing of records.

## Strategy
1. **Analysis**: Inspect the database schema and current data to find constraint violations or data issues.
2. **Setup**: Create a reproduction script to trigger the failure.
3. **Fix**: Update `DedupRepository.batch_add_media_signatures` to handle the specific error or data condition.
4. **Verify**: Ensure batch writes work correctly with the fix.

## Phased Checklist

### Phase 1: Investigation
- [x] Inspect `media_signatures` table schema and indexes.
- [x] Analyze the `INS` error code (likely related to IntegrityError or SQL syntax).
- [x] Create a reproduction script in `tests/temp/`.

### Phase 2: Implementation & Fix
- [x] Update `repositories/dedup_repo.py` to fix the batch insertion logic.
- [x] Improve error logging to show the full exception stack/message.
- [x] Add better data validation before insertion.

### Phase 3: Verification
- [x] Run the reproduction script to verify the fix.
- [x] Run existing deduplication unit tests.
- [x] Verify that no new errors appear in logs.
