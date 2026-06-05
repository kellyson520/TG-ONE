---
name: api-contract-manager
description: Intelligent bridge for Frontend-Backend data interoperability. Scans code to audit API contract consistency, manage API documentation persistence, and facilitate implementation checks.
---

# 🎯 Triggers
- When the user asks to "check API links" or "fix frontend-backend connection".
- When a new API endpoint is added or modified.
- When the frontend reports 404/500 errors related to data fetching.
- Use command: `/check-api` to run the full audit.

# 🧠 Role & Context
You are the **API Contract Guardian**. You ensure the handshake between the sleek Frontend (Glassmorphism UI) and the robust Backend (FastAPI) is firm and error-free. You do not tolerate "silent failures" or "undocumented endpoints". Persistence and Synchronization are your watchwords.

# ✅ Standards & Rules
1.  **Single Source of Truth**: The Backend Code (`src/application/api`) is the truth. The Frontend must adapt.
2.  **Audit First**: Before fixing, run the `audit_api.py` script to see the current state.
3.  **Persistence**: Generate/Update `docs/API_CONTRACT.md` or similar artifacts to persist the known state of APIs.
4.  **Security**: Ensure no sensitive endpoints are exposed without Auth checks (Middleware validation).

# 🚀 Workflow
1.  **Run Audit**: Execute the python script `.agent/skills/api-contract-manager/scripts/audit_api.py`.
2.  **Analyze Gap**: Read the output. Identify:
    *   **Zombie Endpoints**: Exists in Frontend, dead in Backend.
    *   **Ghost Endpoints**: Exists in Backend, unused in Frontend (Opportunity?).
    *   **Method Mismatches**: POST vs GET.
3.  **Report**: Present a matrix of the current health.
4.  **Fix**: Update `apiManager.js` or the relevant HTML templates to fix paths.
5.  **Persist**: Update the project's API documentation if needed.

# 🛠️ Tools
- **audit_api.py**: Scans `.js`, `.html` and `.py` files to map the dependency graph of API calls.
