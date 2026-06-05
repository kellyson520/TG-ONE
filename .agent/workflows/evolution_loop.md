---
description: Fully automated closed-loop evolution workflow (Problem -> Solve -> Report -> Evolve -> Loop)
---

# Closed Loop Evolution Cycle

This workflow defines the "Super Loop" for the TG ONE system, ensuring that every task either uses an existing skill or contributes to creating/improving one.

## Phase 1: Ingestion & Skill Selection
1.  **Analyze Request**: Read the user's request.
2.  **Skill Match**:
    -   Check `AGENTS.md` and `.agent/skills/`.
    -   **HIT**: If a skill matches, use `view_file` on its `SKILL.md` and execute.
    -   **MISS**: Proceed to Phase 2 (Manual Solve).

## Phase 2: Execution (The "Solve" Loop)
### Case A: Skill Execution
1.  Execute the skill's defined workflow.
2.  **Success**: Go to Phase 4 (Report).
3.  **Failure**:
    -   Log failure to `todo.md` (e.g., "Attempted skill X, failed due to Y").
    -   Switch to Manual Mode (Case B).

### Case B: Manual Execution (Standard PSB)
1.  Plan: `task-lifecycle-manager` -> Init `Workstream`.
2.  Build: Write Code, Tests.
3.  Verify: Run Tests.

## Phase 3: Evolution (The Feedback Loop)
**Trigger**: Upon successful completion of Phase 2 (Manual or Skill-Repair).

1.  **Repair Check**:
    -   Did a skill fail in Phase 2?
    -   **YES**: Execute `skill-evolution` (Repair Mode). Update the skill's script or prompt to handle the failure case.

2.  **Mining Check**:
    -   Was this Manual Execution repetitive?
    -   **YES**: Execute `skill-evolution` (Mining Mode). Scaffold a new skill using the successful manual steps.

## Phase 4: Closure & Finalization
1.  Write `report.md`.
2.  Update `docs/process.md`.
3.  **Recursion**: The output of this loop (New Skill) is now available for Phase 1 of the next Request.

## Operational Command
To enforce this loop, the Agent must ask:
> "Did we learn something new? Is there a skill to fix or create?"
before closing ANY task.
