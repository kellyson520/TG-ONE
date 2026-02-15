# Task: Repair Access Log Display and Task Queue Timezone

## Status
- [x] Investigate Access Log issue (kellyson LOGIN_FAILED display)
- [x] Investigate Task Queue Timezone issue (Latency/Missing recent logs)
- [x] Fix Access Log (Frontend/Backend)
- [x] Fix Task Queue Timezone (Frontend/Backend)
- [x] Verify both fixes
- [x] Documentation Update

## Context
User reports two issues:
1. Access Log page shows raw or problematic log entry: `2026/2/15 10:15:56 kellyson LOGIN_FAILED ...`.
2. Task Queue / Execution Record has latency issues, showing times hours ago (e.g. 10:53 UTC vs 16:00 Local), suggesting a timezone display mismatch.

## Plan
1. Analyze `web_admin/frontend/src/pages/Logs.tsx` and `AuditLogs.tsx` to understand log rendering.
2. Analyze `web_admin/frontend/src/pages/Tasks.tsx` to understand timestamp rendering.
3. Check `web_admin/routers` for how datetimes are returned (UTC vs Local).
4. Implement timezone conversion on Frontend (or ensure Backend returns ISO with timezone info).
5. Fix the Access Log parsing if it's failing on that specific line.
