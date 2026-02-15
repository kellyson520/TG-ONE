# Task: Remove Fake Access & Implement Real Backend Integration

## Phase 1: Plan
- [x] Analyze mock data in frontend store (`store/index.ts`)
- [x] Analyze mock logic in Login page (`pages/Login.tsx`)
- [x] Identify backend API endpoints for Auth and Stats
- [ ] Create API service layer in frontend
- [ ] Design real state management flow

## Phase 2: Setup
- [x] Verify backend server capability
- [x] Setup Axios/Fetch client with interceptors for JWT/Cookies
- [x] Synchronize `docs/tree.md`

## Phase 3: Build
- [x] Implement `src/lib/api-client.ts` for unified API calls
- [ ] Implement `src/services/auth-service.ts`
- [x] Implement `src/services/system-service.ts`
- [ ] Refactor `src/store/index.ts`: Remove `useMockDataStore`, update `useAppStore`
- [ ] Refactor `src/pages/Login.tsx`: Real login integration
- [x] Refactor dashboard components: Replace mock data with real stats from system-service

## Phase 4: Verify
- [ ] Verify login flow with real backend
- [x] Verify dashboard stats update from real backend
- [ ] Check console for API errors or pending mocks
- [ ] Run basic UI integration tests

## Phase 5: Report
- [ ] Generate `report.md`
- [ ] Update `process.md`
- [ ] Archive workstream
