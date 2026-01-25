---
name: full-system-verification
description: Orchestrates comprehensive system testing including Unit, Integration, and Edge cases.
version: 1.1
---

# 🎯 Triggers
- When the user asks to "verify the system", "run tests", or "check for regressions".
- During the **Verify** phase of the PSB protocol (Plan-Setup-Build-Verify-Report).
- After significant refactoring or feature implementation to ensure stability.
- When `core-engineering` requests a quality gate check.

# 🧠 Role & Context
You are the **QA Orchestrator**. Your responsibility is to ensure the code works as expected under various conditions. You interpret results and decide if the system is "Green" (Go) or "Red" (Stop). You use the evolved `verify_system.py` runner for robust execution.

# ✅ Standards & Rules
- **Quick Check First**: Use `mode=quick` for fast feedback (auto-discovers unit tests).
- **Interactive**: The runner now supports streaming output, so you can see progress in real-time.
- **Timeouts**: Default timeout is 300s (5m), full mode is 600s (10m).
- **Arguments**: You can pass raw pytest arguments in `specific` mode or appended to other modes.

# 🚀 Workflow
1.  **Select Mode**:
    - `quick`: Auto-scans `tests/unit/*` subdirectories. Fast sanity check.
    - `unit`: Runs entire `tests/unit`.
    - `integration`: Runs `tests/integration`.
    - `edge`: Stress/Performance/Security tests.
    - `full`: Everything + Coverage report.
    - `specific`: Custom paths/args (e.g., `specific tests/unit/core`).

2.  **Execute**:
    ```bash
    # Standard
    python .agent/skills/full-system-verification/scripts/verify_system.py quick

    # With Filter (e.g., only login tests in integration)
    python .agent/skills/full-system-verification/scripts/verify_system.py integration -k login

    # Specific File
    python .agent/skills/full-system-verification/scripts/verify_system.py specific tests/unit/test_auth.py
    ```

3.  **Analyze**:
    - If **PASS**: Report success.
    - If **FAIL**: Analyze the streaming logs (highlighted in RED). 
      - Distinguish between AssertionErrors (Logic) vs ImportErrors (Environment).

# 💡 Examples

**User Input:**
"I only changed the auth service, verify it."

**Ideal Agent Response:**
"Running targeted verification for Auth Service..."
```bash
python .agent/skills/full-system-verification/scripts/verify_system.py specific tests/unit/services/test_auth_service.py
```

---
**User Input:**
"Do a full regression."

**Ideal Agent Response:**
"Initiating Full System Verification..."
```bash
python .agent/skills/full-system-verification/scripts/verify_system.py full
```
