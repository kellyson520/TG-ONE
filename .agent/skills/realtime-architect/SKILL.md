---
name: realtime-architect
description: Standardized Full-Stack WebSocket Architecture for Real-time Systems
version: 1.0
---

# 🎯 Triggers (触发条件)
- When implementing features requiring instant updates (e.g., Dashboards, Chat, Progress Bars, Logs).
- When replacing polling loops (`setInterval`) with push notifications.
- When designing WebSocket protocols or infrastructure.
- When debugging WebSocket connection issues or message loss.

# 🧠 Role & Context (角色设定)
You are the **Real-time Systems Architect**. You design robust, scalable, and resilient websocket solutions. You prioritize **Reliability** (Reconnect/Heartbeat) over raw speed, and always ensure a **Graceful Fallback** (Polling) exists for unstable networks.

# ✅ Standards & Rules (执行标准)

## 1. Architecture Pattern (Hybrid)
- **Primary**: WebSocket for real-time events.
- **Fallback**: Auto-switch to Polling if WebSocket fails (>3 reconnect attempts).
- **Structure**: Backend `ConnectionManager` <-> Frontend `WebSocketManager`.

## 2. Protocol Specification (JSON)
All messages MUST follow this structure:
```json
// Server -> Client
{
  "type": "event_type",   // e.g., "stats_update", "log", "pong"
  "topic": "channel_name", // e.g., "stats", "system"
  "data": { ... },        // Payload
  "timestamp": 1234567890
}

// Client -> Server
{
  "action": "subscribe",  // e.g., "subscribe", "unsubscribe", "ping"
  "topic": "channel_name"
}
```

## 3. Backend Implementation (FastAPI)
- **Singleton Manager**: Use a global `ConnectionManager` instance.
- **Pub/Sub**: Support topic-based subscription (`manager.subscribe(client_id, topic)`).
- **Throttling**: For high-frequency events (e.g., logs/stats), implement a throttle (e.g., 100ms) to prevent frontend flooding.
- **EventBus Integration**: Hook into system EventBus to auto-broadcast domain events.

## 4. Frontend Implementation (Vanilla JS)
- **Singleton**: `window.wsManager` (Global Instance).
- **Life-cycle**:
  - `initWebSocket()`: Connect and setup listeners.
  - `startPolling()` / `stopPolling()`: Toggle fallback mechanism.
  - `beforeunload`: Close connection gracefully.
- **Visual Feedback**:
  - Show connection status (Pulse Dot: Green=Connected, Red=Disconnected).
  - Use Animations (`animate-fade-in`, `animate-pulse`) for incoming data.

# 🚀 Workflow (工作流)

1.  **Define Topics**:
    - Identify data streams (e.g., `logs`, `stats`, `tasks`).
    - Add topic constants to Backend `ConnectionManager` and Frontend.

2.  **Backend Implementation**:
    - Ensure `websocket_router.py` handles the new topic.
    - Add `broadcast_{topic}_update` helper function.
    - Hook into Business Logic (Service Layer) to trigger broadcast.

3.  **Frontend Integration**:
    - **Step 3.1**: Check `wsManager` availability.
    - **Step 3.2**: Implement `handle{Topic}Update(msg)` function.
    - **Step 3.3**: Subscribe on connect: `wsManager.subscribe('topic', handler)`.
    - **Step 3.4**: Implement `updateUI` logic (partial DOM update, NOT page reload).
    - **Step 3.5**: Add Polling Fallback logic.

4.  **Verification**:
    - Verify Heartbeat (Ping/Pong every 30s).
    - Verify Reconnect (Kill backend, restart, frontend should auto-reconnect).
    - Verify Fallback (Block WS port, frontend should switch to polling).

# 💡 Examples (代码片段)

## Frontend Handler Pattern
```javascript
function initRealtime() {
    if (!window.wsManager) { startPolling(); return; }
    
    wsManager.onConnect(() => {
        stopPolling();
        wsManager.subscribe('dashboard_stats', (msg) => {
            if (msg.type === 'update') updateDashboard(msg.data);
        });
    });
    
    wsManager.onDisconnect(() => {
        startPolling(); // Graceful degradation
    });
}
```

## Backend Broadcast Pattern
```python
# In Service Layer
await container.event_bus.emit(
    "stats_update", 
    {"cpu": 45.2, "mem": 60.1}
)

# In WebSocket Router (hooked via EventBus)
if event_name == "stats_update":
    await manager.broadcast("stats", {"type": "stats", "data": event_data})
```
