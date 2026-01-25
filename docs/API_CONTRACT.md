# API Contract Status Report
**Last Scan:** lihuo (Automated)

## Summary
- **Backend Endpoints**: 97
- **Frontend Calls**: 26
- **Health**: ✅ Excellent

## Backend Inventory
| Method | Path | Source File |
|---|---|---|
| GET | `/` | `web_admin\routers\page_router.py` |
| POST | `/api/auth/2fa/disable` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/2fa/enable` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/2fa/recovery-codes` | `web_admin\routers\auth_router.py` |
| GET | `/api/auth/2fa/recovery-codes/status` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/2fa/recovery-codes/verify` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/2fa/setup` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/check_password_strength` | `web_admin\routers\auth_router.py` |
| GET | `/api/auth/lockout_status` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/login` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/login/2fa` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/login/recovery` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/logout` | `web_admin\routers\auth_router.py` |
| GET | `/api/auth/rate_limiter_stats` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/refresh` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/register` | `web_admin\routers\auth_router.py` |
| GET | `/api/auth/sessions` | `web_admin\routers\auth_router.py` |
| DELETE | `/api/auth/sessions/user/{user_id}` | `web_admin\routers\auth_router.py` |
| DELETE | `/api/auth/sessions/{session_id}` | `web_admin\routers\auth_router.py` |
| POST | `/api/auth/unlock_account` | `web_admin\routers\auth_router.py` |
| GET | `/api/chats` | `web_admin\fastapi_app.py` |
| GET | `/api/error_logs` | `web_admin\fastapi_app.py` |
| GET | `/api/logs/download` | `web_admin\fastapi_app.py` |
| GET | `/api/logs/files` | `web_admin\fastapi_app.py` |
| GET | `/api/logs/tail` | `web_admin\fastapi_app.py` |
| GET | `/api/rules/chats` | `web_admin\routers\rule_router.py` |
| GET | `/api/rules/logs` | `web_admin\routers\rule_router.py` |
| GET | `/api/rules/visualization` | `web_admin\routers\rule_router.py` |
| GET | `/api/rules/{rule_id}` | `web_admin\routers\rule_router.py` |
| DELETE | `/api/rules/{rule_id}` | `web_admin\routers\rule_router.py` |
| PUT | `/api/rules/{rule_id}` | `web_admin\routers\rule_router.py` |
| POST | `/api/rules/{rule_id}/keywords` | `web_admin\routers\rule_router.py` |
| DELETE | `/api/rules/{rule_id}/keywords` | `web_admin\routers\rule_router.py` |
| POST | `/api/rules/{rule_id}/replace-rules` | `web_admin\routers\rule_router.py` |
| DELETE | `/api/rules/{rule_id}/replace-rules` | `web_admin\routers\rule_router.py` |
| POST | `/api/rules/{rule_id}/toggle` | `web_admin\fastapi_app.py` |
| POST | `/api/rules/{rule_id}/toggle` | `web_admin\routers\rule_router.py` |
| GET | `/api/security/acl` | `web_admin\routers\security_router.py` |
| POST | `/api/security/acl` | `web_admin\routers\security_router.py` |
| DELETE | `/api/security/acl/{ip_address}` | `web_admin\routers\security_router.py` |
| GET | `/api/settings/meta` | `web_admin\routers\settings_router.py` |
| GET | `/api/stats/distribution` | `web_admin\routers\stats_router.py` |
| GET | `/api/stats/overview` | `web_admin\routers\stats_router.py` |
| GET | `/api/stats/series` | `web_admin\routers\stats_router.py` |
| GET | `/api/stats/system` | `web_admin\routers\stats_router.py` |
| GET | `/api/stats/system_resources` | `web_admin\routers\stats_router.py` |
| GET | `/api/system/archive-status` | `web_admin\routers\system_router.py` |
| POST | `/api/system/archive/trigger` | `web_admin\routers\system_router.py` |
| GET | `/api/system/audit/logs` | `web_admin\routers\system_router.py` |
| GET | `/api/system/backups` | `web_admin\routers\system_router.py` |
| POST | `/api/system/backups/trigger` | `web_admin\routers\system_router.py` |
| GET | `/api/system/config` | `web_admin\routers\system_router.py` |
| POST | `/api/system/config` | `web_admin\routers\system_router.py` |
| GET | `/api/system/db-pool` | `web_admin\routers\system_router.py` |
| GET | `/api/system/eventbus/stats` | `web_admin\routers\system_router.py` |
| GET | `/api/system/exceptions/stats` | `web_admin\routers\system_router.py` |
| GET | `/api/system/logs/download` | `web_admin\routers\system_router.py` |
| GET | `/api/system/logs/error_logs` | `web_admin\routers\system_router.py` |
| GET | `/api/system/logs/list` | `web_admin\routers\system_router.py` |
| GET | `/api/system/logs/view` | `web_admin\routers\system_router.py` |
| POST | `/api/system/reload` | `web_admin\routers\system_router.py` |
| POST | `/api/system/restart` | `web_admin\routers\system_router.py` |
| GET | `/api/system/settings` | `web_admin\routers\system_router.py` |
| PUT | `/api/system/settings` | `web_admin\routers\system_router.py` |
| GET | `/api/system/stats` | `web_admin\routers\system_router.py` |
| GET | `/api/system/stats_fragment` | `web_admin\routers\system_router.py` |
| GET | `/api/system/tasks` | `web_admin\routers\system_router.py` |
| GET | `/api/system/trace/download` | `web_admin\routers\system_router.py` |
| GET | `/api/system/websocket/stats` | `web_admin\routers\system_router.py` |
| GET | `/api/users/me` | `web_admin\routers\user_router.py` |
| GET | `/api/users/settings` | `web_admin\routers\user_router.py` |
| POST | `/api/users/settings` | `web_admin\routers\user_router.py` |
| DELETE | `/api/users/{user_id}` | `web_admin\routers\user_router.py` |
| POST | `/api/users/{user_id}/toggle_active` | `web_admin\routers\user_router.py` |
| POST | `/api/users/{user_id}/toggle_admin` | `web_admin\routers\user_router.py` |
| GET | `/api/visualization/graph` | `web_admin\fastapi_app.py` |
| GET | `/archive` | `web_admin\routers\page_router.py` |
| GET | `/audit_logs` | `web_admin\routers\page_router.py` |
| GET | `/dashboard` | `web_admin\routers\page_router.py` |
| GET | `/downloads` | `web_admin\routers\page_router.py` |
| GET | `/healthz` | `web_admin\fastapi_app.py` |
| GET | `/history` | `web_admin\routers\page_router.py` |
| GET | `/login` | `web_admin\routers\page_router.py` |
| GET | `/logout` | `web_admin\routers\page_router.py` |
| GET | `/logs` | `web_admin\routers\page_router.py` |
| GET | `/metrics` | `web_admin\fastapi_app.py` |
| GET | `/readyz` | `web_admin\fastapi_app.py` |
| GET | `/register` | `web_admin\routers\page_router.py` |
| GET | `/rules` | `web_admin\routers\page_router.py` |
| GET | `/security` | `web_admin\routers\page_router.py` |
| GET | `/series` | `web_admin\fastapi_app.py` |
| GET | `/settings` | `web_admin\routers\page_router.py` |
| POST | `/simulate` | `web_admin\routers\simulator_router.py` |
| GET | `/tasks` | `web_admin\routers\page_router.py` |
| GET | `/users` | `web_admin\routers\page_router.py` |
| GET | `/visualization` | `web_admin\routers\page_router.py` |
| GET | `/ws/stats` | `web_admin\routers\websocket_router.py` |
