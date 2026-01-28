---
description: Ship code to production (Local CI -> Git Push)
---

1. Execute Local CI verification.
    - If the user hasn't specified a test file, ask them for one, or use your best judgement based on edited files.
    - Run: `python scripts/local_ci.py --test <test_file_path>`
    - If checks fail, STOP and Help User Fix.

2. If CI Passes, use `git-manager` to clean, commit and push.
    - `python scripts/cleanup.py` (if exists, or use workspace-hygiene)
    - Commit with conventional message.
    - Push to current branch.

3. Final Report.
    - Confirm "Code Shipped" and update Todo status.
