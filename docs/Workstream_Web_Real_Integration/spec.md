# Specification: Frontend Real Backend Integration

## Background
The current frontend uses ZUSTAND stores with hardcoded mock data and simulated API delays in the Login page. This needs to be replaced with real backend integration to ensure the system is functional and secure.

## Technical Objectives
1. **Authentication**: Use `/api/auth/login` for credentials and handle 2FA via `/api/auth/login/2fa` if required.
2. **State Management**: Persist only necessary UI state (theme, sidebar). System metrics and user stats should be fetched from the backend.
3. **API Service Layer**: Use unified API client to handle request/response transformation and error handling.
4. **Real-time Data**: (Optional but recommended) Transition stats to WebSocket if backend supports it, otherwise use polling.

## Proposed Changes

### 1. API Client (`src/lib/api-client.ts`)
- Use `fetch` or `axios`.
- Handle CSRF/Tokens if necessary (Backend currently uses HttpOnly cookies for JWT).
- Standardize response format matching `ResponseSchema` from backend.

### 2. Store Refactoring (`src/store/index.ts`)
- **Remove** `useMockDataStore`.
- **Update** `useAppStore`:
    - Remove placeholder user data.
    - Add `checkAuth` method to verify session on app load.
    - Integrate `systemMetrics` fetching logic (or keep it as setter for periodic updates).

### 3. Login Page Refactoring (`src/pages/Login.tsx`)
- Implement real POST request to `/api/auth/login`.
- Handle `202 ACCEPTED` for 2FA requirement.
- Display backend error messages (e.g., account locked, invalid credentials).

### 4. Dashboard Stats
- Use `src/services/system-service.ts` to fetch stats from `/api/system/stats`.
- Map backend fields:
    - `data.rules.active` -> `activeRules`
    - `data.forwards.today` -> `todayForwards`
    - `data.dedup.total_cached` -> `dedupCache`

## Quality Gates
- No "Simulated API call" comments remaining.
- Login works with valid DB users.
- Dashboard shows 0s if backend is unreachable, not hardcoded dummy numbers.
