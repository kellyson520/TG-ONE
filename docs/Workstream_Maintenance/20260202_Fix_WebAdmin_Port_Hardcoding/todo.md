# Fix Web Admin Port Hardcoding

## Context
User asked: "Why is the web service on 8080 when I set 9000?".
Investigation found that `web_admin/run.py` has `port=8080` hardcoded, ignoring `settings.WEB_PORT`.
Additionally, `docker-compose.yml` maps host `9810` to container `9000`, so the container MUST listen on 9000 for this to work.

## Root Cause Analysis
1.  `web_admin/run.py` hardcodes port 8080.
2.  `docker-compose.yml` expects port 9000.
3.  User might have confused `HEALTH_PORT=9000` with `WEB_PORT`, or intended to set `WEB_PORT` but the hardcoding prevented it from working.

## Implementation Plan
1.  Modify `web_admin/run.py` to import `settings` from `core.config`.
2.  Update `app.run(...)` to use `settings.WEB_PORT` and `settings.WEB_HOST`.
3.  Update env/config to ensure `WEB_PORT` defaults to 9000 if that is the intent, or instruct user to set it.
    *Actually*, standard `docker-compose` maps internal 9000. So we should probably default `WEB_PORT` to 9000 in the code or `.env` if we want it to match `docker-compose`. But better to just let it read from config.

## Checklist
### Phase 1: Fix
- [x] Modify `web_admin/run.py` to use dynamic configuration.

### Phase 2: Documentation
- [x] Create `report.md`.
