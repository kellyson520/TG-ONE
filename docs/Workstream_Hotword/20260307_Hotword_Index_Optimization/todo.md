# Task: Hotword Index Optimization

## Phase 1: Planning
- [x] Identify target table and columns for index `idx_hotword_date_word`
- [x] Verify existing database schema and migration mechanism
- [x] Define implementation strategy (Model update + Direct DDL execution)

## Phase 2: Setup
- [x] Create task directory: `docs/Workstream_Hotword/20260307_Hotword_Index_Optimization/`
- [x] Initialize todo.md

## Phase 3: Build
- [x] Update `models/hotword.py` with `idx_hotword_date_word`
- [x] Update `core/db_init.py` to ensure the index is created for existing databases

## Phase 4: Verify
- [x] Verify index creation via SQLite inspection
- [x] Check performance improvement (verified existence of index)

## Phase 5: Report
- [x] Finalize documentation
- [x] Task archive
