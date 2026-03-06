# Task: Improve Hotword Module Error Logging

## Phase 1: Enhance Repository Logging
- [ ] Update `repositories/hotword_repo.py`:
    - [ ] `save_temp_counts`: Add error handling for writing, include path in logs.
    - [ ] `load_rankings`: Use `log_error` with full path.
    - [ ] `load_config`: Use `log_error` with full path.
    - [ ] `save_config`: Use `log_error` with full path.
    - [ ] `atomic_rename`: Use `log_error` including source/target.

## Phase 2: Enhance Service Logging
- [ ] Update `services/hotword_service.py`:
    - [ ] `process_batch`: Use `log_error` with channel name and items count.
    - [ ] `flush_to_disk`: Log cache flushing with details.
    - [ ] `aggregate_period`: Log each step and merge results.
    - [ ] `HotwordAnalyzer`: Use standard logging methods for engine initialization.

## Phase 3: Verification
- [ ] Run `local_ci.py` to ensure no syntax/import errors.
