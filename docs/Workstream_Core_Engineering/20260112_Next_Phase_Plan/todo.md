# 下一阶段任务规划 (Next Phase Planning)

> **创建日期**: 2026-01-11  
> **规划周期**: 2026-01-12 ~ 2026-01-18  
> **状态**: 📋 规划中

---

## 🎯 目标总览

基于当前项目状态分析，规划 6 个任务阶段，涵盖清理、安全收尾、功能增强、可视化优化、移动端适配和监控增强。

---

## 📋 Phase A: 紧急清理 (Immediate Cleanup) - 0.5h ✅

**优先级**: 🔴 紧急  
**目标**: 清理根目录测试产物，保持工程洁净  
**状态**: ✅ 已完成 (2026-01-11 21:27)

- [x] **A.1 移除测试产物**
    - 删除 `test_*.txt` 文件 (24 个) ✅
    - 删除 `*.log` 日志文件 (2 个) ✅
    - 终止了 32 个僵尸 pytest 进程 ✅
- [x] **A.2 清理 MagicMock 临时目录**
    - 检查 `MagicMock/` 目录内容 ✅
    - 已删除 ✅
- [x] **A.3 更新 docs/tree.md**
    - 执行 `tree /F` 命令同步文档 ✅

---

## 📋 Phase B: 安全收尾 (Security Finalization) - 4h ✅

**优先级**: 🟠 高  
**Workstream**: `20260112_Security_Phase3_Finalize`  
**状态**: ✅ 已完成 (2026-01-11 21:35)

- [x] **B.1 Recovery Codes (备份码)** ✅
    - [x] 生成 10 个一次性备份码 (格式: XXXX-XXXX)
    - [x] 密码哈希后存入 `backup_codes` JSON 字段
    - [x] API: `POST /api/auth/2fa/recovery-codes` 生成
    - [x] API: `GET /api/auth/2fa/recovery-codes/status` 状态查询
    - [x] API: `POST /api/auth/2fa/recovery-codes/verify` 验证
    - [x] API: `POST /api/auth/login/recovery` 使用备份码登录
    - [x] 单元测试: 10/10 通过
- [~] **B.2 2FA 强制策略 (Admin Only)** ⏭️ 跳过
    - 用户要求不强制开启 2FA
- [x] **B.3 审计日志增强** ✅
    - [x] 记录 2FA 启用/禁用/验证失败事件 (已在 auth_router)
    - [x] 记录 Recovery Code 生成/使用事件
    - [x] 记录 IP Guard 拦截事件 (ip_guard_middleware)

---

## 📋 Phase C: 通知系统集成 (Notification Integration) - 6h

**优先级**: 🟡 中  
**Workstream**: `20260112_Notification_Integration`

- [ ] **C.1 WebSocket 通知广播**
    - 新增 `notification` topic 至 `/ws/realtime`
    - 后端事件: 规则变更、异常告警、定时任务完成
- [ ] **C.2 前端 Toast 通知组件**
    - 扩展 `Toast.vue` 支持 WebSocket 订阅
    - 支持 Info/Success/Warning/Error 级别
- [ ] **C.3 邮件/Telegram 通知 (可选)**
    - 配置 SMTP 发送邮件告警
    - 复用已有 Telegram Bot 发送管理员消息

---

## 📋 Phase D: 规则管理可视化 (Rule Flow Visualization) - 8h

**优先级**: 🟡 中  
**Workstream**: `20260113_Rule_Flow_Visualization`

- [ ] **D.1 规则流程图 (Flow Diagram)**
    - 使用 `Vue Flow` 或 `dagre-d3` 可视化规则触发链路
    - 展示: Source → Filters → Middlewares → Sender
- [ ] **D.2 规则模拟器 (Rule Simulator)**
    - 输入测试消息文本
    - 模拟执行并显示每个 Filter 的匹配结果
- [ ] **D.3 规则批量导入/导出优化**
    - 支持 YAML/JSON 格式
    - 前端拖拽上传

---

## 📋 Phase E: 移动端 PWA 增强 (Mobile PWA Enhancement) - 4h

**优先级**: 🟢 低  
**Workstream**: `20260113_Mobile_PWA_Enhancement`

- [ ] **E.1 PWA Manifest & Service Worker**
    - 添加 `manifest.json`
    - 配置 Vite PWA 插件
- [ ] **E.2 离线模式支持 (Partial)**
    - 缓存静态资源
    - 离线时显示最后已知状态
- [ ] **E.3 添加至主屏幕**
    - iOS/Android 图标配置
    - 启动动画 (Splash Screen)

---

## 📋 Phase F: 系统监控增强 (Monitoring Dashboard) - 5h

**优先级**: 🟢 低  
**Workstream**: `20260114_Monitoring_Dashboard`

- [ ] **F.1 Metrics API**
    - `/api/system/metrics`: CPU/Memory/Disk/Network
    - 使用 `psutil` 采集
- [ ] **F.2 实时图表**
    - ECharts 实时折线图 (30s sliding window)
    - 告警阈值线
- [ ] **F.3 历史数据存储 (可选)**
    - 基于 SQLite 的简易 TSDB
    - 保留最近 24h 数据

---

## 📋 Phase G: 全局事件日志与异常智能化 - 6h ⭐ NEW

**优先级**: 🟠 高  
**Workstream**: `20260112_Event_Log_Enhancement`

### G.1 全局事件日志增强 ✅
- [x] **统一事件总线 (EventBus) 日志钩子** ✅
    - 在 `core/event_bus.py` 添加日志 Middleware
    - 记录所有 `FORWARD_*`, `ERROR_*`, `SYSTEM_*`, `AUTH_*`, `RULE_*` 事件
    - 支持按级别过滤 + 通配符订阅
- [x] **EventBus 统计 API** ✅
    - `/api/system/eventbus/stats` 查看事件计数
- [ ] **转发日志存档记录加强** (待完成)
    - 扩展 `stats_repo.log_action()` 记录更多字段
    - 新增字段: `source_chat_title`, `target_chat_title`, `filter_hit`, `ai_modified`
    - 创建 `forward_logs` 独立表 (高频写入优化)

### G.2 全局异常捕捉 ✅
- [x] **创建 `GlobalExceptionHandler` 服务** ✅
    - 位置: `services/exception_handler.py`
    - 捕捉未处理异常并记录到审计日志
    - 支持异常聚合 (相同异常 10 分钟内只记录一次)
- [x] **异步任务异常捕捉** ✅
    - 改进 `exception_handler.create_task()` 包装器
    - 自动捕捉并记录 Task 异常
- [x] **异常统计 API** ✅
    - `/api/system/exceptions/stats` 查看异常聚合
- [ ] **Telegram 事件异常隔离** (待完成)
    - 单条消息处理失败不影响其他消息
    - 失败消息进入重试队列

### G.3 全局广播智能化 ✅
- [x] **WebSocket 广播增强** ✅
    - 在 `web_admin/routers/websocket_router.py` 增强 ConnectionManager
    - 统一管理 `/ws/realtime` 的多 topic 广播
    - 支持 topic: `stats`, `rules`, `system`, `logs`, `alerts`, `notifications`
- [x] **事件驱动广播** ✅
    - EventBus 事件自动触发 WebSocket 广播
    - 例: `FORWARD_SUCCESS` → 广播到 `stats` topic
- [x] **智能节流 (Throttling)** ✅
    - 高频事件合并广播 (100ms 内相同类型事件合并)
    - 防止 WebSocket 消息风暴

---

## 📋 Phase H: 架构深度优化 - 8h ⭐ NEW

**优先级**: 🔴 紧急  
**Workstream**: `20260112_Architecture_Optimization`

### H.1 数据库连接池优化 ✅
- [x] **统一连接池配置** ✅
    - 在 `models/models.py` 的 `get_async_engine()` 中集中配置
    - 默认: `pool_size=20`, `max_overflow=30`
    - 添加环境变量支持: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`
- [x] **连接池监控** ✅
    - 添加 `/api/system/db-pool` 接口查看连接池状态
    - 监控 `pool.checkedout()`, `pool.checkedin()`, `pool.overflow()`
- [ ] **FastAPI + Telegram 连接隔离** (待评估)
    - 评估是否需要为 Web 和 Bot 分离连接池
    - 添加连接超时和重试机制

### H.2 优雅关闭 (Graceful Shutdown) 重构 ✅
- [x] **统一关闭协调器** ✅
    - 创建 `ShutdownCoordinator` 类 (`core/shutdown_coordinator.py`)
    - 定义关闭顺序: Web → Worker → Scheduler → Clients → DB
- [x] **解决竞态条件** ✅
    - 添加 `ShutdownState` 枚举 (RUNNING/STOPPING/STOPPED)
    - 使用 `asyncio.Event` 协调各组件
- [x] **增加关闭超时** ✅
    - 每个组件最多等待 30s
    - 超时后强制终止并记录日志
- [x] **移除重复关闭逻辑** (待集成到 main.py)
    - 统一到 `container.shutdown()` 入口
    - `main.py` 只调用 `ShutdownCoordinator.shutdown()`

### H.3 uvloop 兼容性加固
- [x] **兼容性测试套件** ✅
    - 添加 `tests/compatibility/test_uvloop.py`
    - 测试 SQLAlchemy Async + uvloop
    - 测试 Telethon + uvloop
- [x] **条件启用 uvloop** ✅
    - 只在 Linux 且所有库兼容时启用
    - 添加 `DISABLE_UVLOOP=true` 环境变量开关
- [ ] **事件循环策略统一**
    - 确保所有 `asyncio.get_event_loop()` 调用一致
    - 移除 `loop = asyncio.new_event_loop()` 冗余代码

### H.4 代码高效化/低占用优化
- [x] **_memory_maintenance 任务修复** ✅
    - 移动到 `start_clients()` 内部
    - 使用 `container.services` 管理生命周期
    - 添加到 `asyncio.gather(*tasks)` 中
- [x] **clear_temp_dir 异步化** ✅
    - 使用 `asyncio.to_thread(_clear_temp_dir_sync)` 包装
    - 避免阻塞事件循环
- [x] **register_bot_commands 优化** ✅
    - 添加命令版本检查 (Hash 比对)
    - 只在命令定义变化时重新注册
- [ ] **资源预加载优化** (待完成)
    - 延迟导入重量级模块 (ECharts, AI 模块)
    - 使用 `__getattr__` 实现模块级懒加载

### H.5 转发日志存档优化
- [x] **高性能日志写入** ✅
    - 使用批量 INSERT (每 100 条或每 5 秒)
    - 异步队列缓冲写入
- [x] **日志归档策略** ✅
    - 超过 7 天的日志自动压缩归档
    - 归档文件格式: `forward_logs_YYYYMMDD.db`
- [x] **日志查询优化** ✅
    - 添加复合索引 `(rule_id, timestamp)`
    - 支持按时间范围分区查询

---

## 🗓️ 时间安排 (更新)

| 日期 | 任务 | 预估工时 |
|------|------|----------|
| 01-11 | Phase A (清理) + Phase B (安全) | 4.5h ✅ |
| 01-12 | Phase G (事件日志) + Phase H.1~H.2 (连接池/关闭) | 6h |
| 01-13 | Phase H.3~H.5 (uvloop/优化) + Phase C 启动 | 6h |
| 01-14 | Phase C 收尾 + Phase D 启动 | 4h |
| 01-15~16 | Phase D (规则可视化) | 8h |
| 01-17 | Phase E (PWA) | 4h |
| 01-18 | Phase F (监控) + 复查 | 5h |

**总工时预算**: 37.5h

---

## ⚠️ 技术债务追踪 (更新)

| 债务项 | 来源 | 优先级 | 预估工时 | 状态 |
|--------|------|--------|----------|------|
| 2FA 备份码 | Security Phase 3 | 中 | 3h | ✅ Phase B |
| 根目录测试产物 | PRE-FLIGHT | 高 | 0.5h | ✅ Phase A |
| 数据库连接池混用风险 | 架构审查 | 🔴 高 | 2h | Phase H.1 |
| 优雅关闭竞态条件 | 架构审查 | 🔴 高 | 3h | Phase H.2 |
| uvloop 兼容性 | 架构审查 | 🟡 中 | 2h | Phase H.3 |
| _memory_maintenance 任务位置 | 架构审查 | 🟡 中 | 1h | Phase H.4 |
| clear_temp_dir 阻塞 | 架构审查 | 🟢 低 | 0.5h | Phase H.4 |
| register_bot_commands 重复 | 架构审查 | 🟢 低 | 1h | Phase H.4 |
| 转发日志高频写入 | 性能优化 | 🟡 中 | 2h | Phase H.5 |
| GeoIP 地理位置限制 | Security Phase 3 | 低 | 5h | 待定 |
| 2FA 输入框分块样式 | Security Phase 3 | 低 | 1h | 待定 |

---

*最后更新: 2026-01-11 21:38*
