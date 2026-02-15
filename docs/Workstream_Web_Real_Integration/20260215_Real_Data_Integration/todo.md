# Task: Real Data Integration (Phase 2: Dashboard & Graphics)

## Context
The project is in the final phase of migrating from mock data to real backend APIs. Phase 1 (Core Logs, Task Management) is complete. Phase 2 focuses on visualizing complex data on the Dashboard and Topology map.

## Plan

### 1. Backend Enhancement (Python)
- **Repo Layer**: Extend `StatsRepository`
    - `get_message_type_distribution()`: Aggregate message types (Text/Image/Video etc.)
    - `get_traffic_trend(days=7)`: Daily/Hourly forward success rate & volume
    - `get_recent_activity(limit=10)`: Latest `RuleLog` entries
- **Service Layer**: Update `SystemService` to expose new stats.
- **API Layer**: Update `StatsRouter` to return new data structures.

### 2. Frontend Integration (React)
- **API Client**: Update `statsApi` in `lib/api.ts` to fetch new endpoints.
- **Dashboard Component**:
    - Replace `trafficData` mock with real API data.
    - Replace `messageTypeData` mock with real API data.
    - Replace `activityLogs` mock with real API data.
- **Visualization Component**:
    - Verify `rulesApi.getVisualization` data structure.
    - Ensure nodes/edges reflect actual database state.

### 3. Verification
- Manual verification of data consistency between DB and UI.
- Ensure no console errors or hardcoded mocks remain.
