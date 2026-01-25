# Phase G + H 技术规范

> **创建日期**: 2026-01-11  
> **阶段**: G.1~G.3 + H.1~H.5  
> **状态**: 🔄 进行中

---

## 已实现组件

### 1. GlobalExceptionHandler (`services/exception_handler.py`) ✅

**功能**:
- 异步任务异常捕捉
- 异常聚合 (10 分钟窗口)
- 审计日志集成
- 回调钩子支持

**API**:
```python
from services.exception_handler import exception_handler

# 创建带异常捕捉的任务
exception_handler.create_task(my_coroutine(), name="my_task")

# 装饰器用法
@exception_handler.task_wrapper("my_task")
async def my_task():
    ...

# 获取统计
stats = exception_handler.get_stats()
```

---

### 2. 增强版 ConnectionManager (`web_admin/routers/websocket_router.py`) ✅

**功能**:
- 多 topic 管理 (logs, stats, alerts, notifications, system, rules)
- 智能节流 (100ms 合并)
- EventBus 集成

**Topics**:
| Topic | 用途 |
|-------|------|
| `stats` | 转发统计更新 |
| `rules` | 规则状态变更 |
| `system` | 系统状态变更 |
| `logs` | 系统日志流 |
| `alerts` | 告警通知 |
| `notifications` | 用户通知 |

**API**:
```python
from web_admin.routers.websocket_router import (
    ws_manager,
    broadcast_stats_update,
    broadcast_log,
    broadcast_alert,
    broadcast_event
)

# 广播消息 (带节流)
await broadcast_stats_update({"count": 100}, throttle=True)

# 广播告警
await broadcast_alert("HIGH_CPU", "CPU 使用率过高", "当前 CPU 使用率 95%", severity="warning")

# EventBus 集成
await broadcast_event("FORWARD_SUCCESS", {"rule_id": 1})
```

---

### 3. ShutdownCoordinator (`core/shutdown_coordinator.py`) ✅

**功能**:
- 统一关闭顺序管理
- 超时控制
- 状态机 (RUNNING → STOPPING → STOPPED)

**推荐关闭顺序**:
1. Web Server (10s)
2. Worker Service (30s)
3. Scheduler (15s)
4. Chat Updater (15s)
5. Telegram Clients (10s)
6. Database (15s)

**API**:
```python
from core.shutdown_coordinator import shutdown_coordinator

# 添加关闭阶段
shutdown_coordinator.add_phase("Web Server", web_server.shutdown, timeout=10)
shutdown_coordinator.add_phase("Worker", worker.stop, timeout=30, critical=True)

# 执行关闭
success = await shutdown_coordinator.shutdown()

# 获取报告
report = shutdown_coordinator.get_report()
```

---

### 4. 增强型 EventBus (`core/event_bus.py`) ✅

**新功能**:
- 通配符订阅 (`"*"`)
- 事件日志钩子
- WebSocket 广播集成
- 事件统计

**API**:
```python
from core.event_bus import EventBus

bus = EventBus()

# 通配符订阅
bus.subscribe("*", on_any_event)

# 获取统计
stats = bus.get_stats()

# 禁用广播
bus.set_broadcast_enabled(False)
```

---

## 待实现组件

### 5. 数据库连接池监控 API (H.1)
- [ ] `/api/system/db-pool` 端点
- [ ] 连接池状态可视化

### 6. 转发日志增强表 (G.1)
- [ ] `forward_logs` 独立表
- [ ] 批量写入优化

### 7. main.py 集成
- [ ] 替换 `asyncio.create_task` 为 `exception_handler.create_task`
- [ ] 集成 `ShutdownCoordinator`
- [ ] 异步化 `clear_temp_dir`

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `services/exception_handler.py` | 新增 | 全局异常处理器 |
| `core/shutdown_coordinator.py` | 新增 | 优雅关闭协调器 |
| `core/event_bus.py` | 修改 | 增强: 通配符订阅 + 日志钩子 + WS 广播 |
| `web_admin/routers/websocket_router.py` | 修改 | 增强: 智能节流 + 新 topic + EventBus 集成 |
| `services/authentication_service.py` | 修改 | Recovery Codes |
| `web_admin/routers/auth_router.py` | 修改 | Recovery Codes API |
| `web_admin/middlewares/ip_guard_middleware.py` | 修改 | 审计日志 |
| `tests/unit/services/test_recovery_codes.py` | 新增 | 单元测试 |

---

*最后更新: 2026-01-11 21:45*
