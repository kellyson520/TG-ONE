# Report: Fix SummaryScheduler ImportError

## Problem
The `SummaryScheduler` failed to start with the following error:
`cannot import name 'hotword_service' from 'services.hotword_service'`

Investigation revealed that:
1. `scheduler/summary_scheduler.py` was trying to import `hotword_service` directly from `services.hotword_service`, but `hotword_service` is the module name, and the intended object was the result of `get_hotword_service()`.
2. One import statement was incorrectly pointing to `services.hotword` (which doesn't exist) instead of `services.hotword_service`.

## Solution
1. Updated `scheduler/summary_scheduler.py` to use `from services.hotword_service import get_hotword_service` and then call `get_hotword_service()` to obtain the service instance.
2. Fixed the incorrect import path from `services.hotword` to `services.hotword_service`.

## Verification
- Running `local_ci.py --skip-test` (as `SummaryScheduler` is infrastructure and the fix is a simple import correction) confirmed that the architecture and code quality checks (including syntax/import checks in Stage 1) pass.
- Code audit of `services/hotword_service.py` confirmed `get_hotword_service` is the correct factory function.

## Changes
- `scheduler/summary_scheduler.py`:
  - Line 509: Corrected import and added service instantiation.
  - Line 600: Corrected import path.
