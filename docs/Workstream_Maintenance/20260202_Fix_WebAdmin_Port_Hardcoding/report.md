# Fix Report: Web Admin Port Hardcoding

## Summary
Fixed an issue where `web_admin` forced port 8080 even if configured otherwise.

## Root Cause
- `web_admin/run.py` contained hardcoded `port=8080` in `app.run()`.
- It ignored `core.config.settings.WEB_PORT`.

## Changes
- **File**: `web_admin/run.py`
- **Fix**: Replaced hardcoded values with `settings.WEB_HOST` and `settings.WEB_PORT`.

## Verification
- Code now imports configuration correctly.
- *Note*: Default config is still `8080` in `core/config/__init__.py`. To use port 9000, please set `WEB_PORT=9000` in your `.env` file.

## Action Required
If you want the internal container service to listen on 9000:
1. Open `.env`
2. Add or update: `WEB_PORT=9000`
3. Restart the service.

If you keep `docker-compose.yml` as `9810:9000`, ensure `WEB_PORT=9000` so the internal port matches the container mapping target.
