# Phase 5: Stability, Async Compliance, and Silent Failure Governance

## Context
解决系统不稳定的根源，统一异步标准，强化错误处理。这是架构重构的关键阶段，旨在消除由于同步代码阻塞异步循环、静默失败导致的问题难以排查以及会话管理混乱带来的稳定性隐患。

## Strategy
- **显式化异常**: 消除所有 `except: pass` 模式，引入结构化日志。
- **异步全合规**: 将剩余的阻塞 I/O (requests, threading.Thread) 彻底替换为 `httpx` 和 `asyncio`。
- **服务化 session**: 将 Session 管理从 Utils/Core 移动到专用 Service，并增强健壮性。
- **守护任务统一化**: 废除传统线程守卫，合并至异步 `GuardService`。

## Checklist

### Phase 5.1: 静默失败全域歼灭战 (P0)
- [x] **Utils 审计**: 扫描 `utils/` 中的所有裸 `except:` 捕获，替换为显式异常 + 结构化日志。
- [x] **关键模块修复**:
    - [x] 修复 `utils/processing/rss_parser.py` 中的 Bare Exception。
    - [x] 修复 `utils/processing/simhash.py` 中的 Bare Exception。
- [x] **日志模式审查**:
    - [x] 审查 `dedup_service.py` 中的空日志/静默模式。
    - [x] 审查 `worker_service.py` 中的空日志/静默模式。

### Phase 5.2: 阻塞 I/O 清理与异步合规性 (P1)
- [x] **BatchProcessor 修复**: 将 `get_event_loop` 升级为 `get_running_loop`。
- [x] **requests 彻底替换**: 搜索全项目，将 `requests` 替换为 `httpx`。
    - [x] 内部代理/Web 钩子。
    - [x] RSS 拉取。
- [x] **Web 自引用修复**: 修复 `web_admin/app` 中对 `/healthz` 的同步自调用。
- [x] **日志推送异步化**: 重构 `utils/network/log_push.py` 为异步实现。

### Phase 5.3: 会话 (Session) 架构重构 (P1)
- [x] **迁移 SessionManager**: 将逻辑移动至 `services/session_service.py`。
- [x] **处理器解耦**: 确保 Handlers 仅通过 `SessionService` 交互，不直接触碰底层文件/数据库。
- [x] **系统自愈**: 实现 `ensure_sessions_ok` 影子备份与自愈逻辑。

### Phase 5.4: 守护任务全量异步化
- [x] **守卫逻辑合并**:
    - [x] 废除 `MaintenanceService` 中的 `threading.Thread`。
    - [x] 废除 `DatabaseMonitor` 中的 `threading.Thread`。
    - [x] 统一使用 `asyncio` 任务。
- [x] **系统日志架构清洗**:
    - [x] 移除 `log_config.py` 中的非标准“日志本地化 (Localization)”翻译逻辑。
    - [x] 回归标准结构化日志输出。
- [x] **GuardService 统一调度**: 在 `GuardService` 中合并 Temp Clean, Memory Guard。
