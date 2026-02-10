# Task: Fix Alembic Migration Path

## Problem
The `alembic` migration folder was moved to `tests/temp/alembic` (likely by the `workspace-hygiene` script), which broke database migrations in `UpdateService` because `UpdateService` looks for `e:\重构\TG ONE\alembic` (or `/app/alembic` in Docker).

## Root Cause
`workspace-hygiene` skill does not include `alembic/` in its root directory whitelist.

## Plan
1. [ ] Move `tests/temp/alembic` back to the root directory.
2. [ ] Update `.agent/skills/workspace-hygiene/SKILL.md` to include `alembic/` in the whitelist.
3. [ ] Verify that `alembic` commands work again.
4. [ ] Verify `UpdateService` bootstrap process.
