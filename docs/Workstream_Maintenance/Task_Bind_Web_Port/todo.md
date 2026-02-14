# Task: Binding Web Interface to Docker Port

## Context
- User wants the web interface to bind to the port defined in `docker-compose.yml`.
- `docker-compose.yml` port mapping: `9810:9000`.
- Host port: 9810.
- Container port: 9000.
- Current `WEB_PORT` default is 8080.
- `.env` has `HEALTH_PORT=9000` but no `WEB_PORT`.

## Implementation Plan
1.  Update `core/config/__init__.py`: Change default `WEB_PORT` to 9000.
2.  Update `.env`: Set `WEB_PORT=9000`.
3.  Synchronize `HEALTH_PORT` if necessary (will keep it as 9000 as it's already there and likely refers to the same service port in the user's mind, or just a placeholder).

## Success Criteria
- The backend application starts and listens on port 9000.
- Port 9810 on host correctly maps to the web admin interface.
