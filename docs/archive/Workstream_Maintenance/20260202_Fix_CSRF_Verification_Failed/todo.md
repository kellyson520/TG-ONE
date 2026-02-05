# Fix CSRF Verification Failed

## Context
User reported "CSRF Token Verification Failed" (403 Forbidden) when logging in via the Web Admin interface.
The request was to `/api/auth/login` (POST).

## Root Cause
The `web_admin/templates/login.html` uses `fetch` to send a JSON POST request for login.
The backend `CSRFMiddleware` requires `X-CSRF-Token` header for non-safe methods.
The `login.html` script fails to read the CSRF token (which IS present in a hidden input) and fails to send it in the request headers.

## Implementation Plan
1.  Modify `web_admin/templates/login.html` JavaScript.
2.  Extract `csrf_token` from the hidden input `name="csrf_token"`.
3.  Inject `X-CSRF-Token` header into both `/api/auth/login` and `/api/auth/login/2fa` fetch calls.

## Verification
- Code review: Ensure header is added.
- Logic check: `csrf_token_input` renders the hidden field, JS reads it, Middleware validates header.

