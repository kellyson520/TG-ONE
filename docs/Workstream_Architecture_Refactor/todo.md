这份计划经过了重新编排，**严格遵循优先级（P0 > P1 > P2）逻辑**。

**调整逻辑说明：**

1. **紧急修复 (P0)**：优先解决循环依赖、目录结构混乱、上帝文件 (`main.py`) 以及最危险的数据库 ORM 泄露问题。这是架构的基石。
2. **核心解耦 (P1)**：解决 Utils 业务泄露、服务层标准化、异步阻塞清理。
3. **功能重构 (P1)**：Web 路由拆分、具体模块（RSS/UFB）的归口。
4. **优化与稳健 (P2)**：性能优化、算法改进、文档与测试。

---

# 架构重构与优化计划 (按优先级重排版)

## 阶段 1：诊断与分析 [已完成/保留]

*(此部分为已完成的历史记录，保持原样作为参考)*

* [x] **结构审计** (完成：识别出 Manager 层冗余及 Utils 业务泄露)
* [x] 分析 `managers/`、`services/` 和 `core/` 之间的重叠情况。
* [x] 审查 `zhuanfaji/` 和 `rss/`，评估整合方案。
* [x] 识别 `utils/` 中的重复工具函数。


* [x] **存储层与 Web 审计** [新增]
* [ ] **发现**: `RuleRepository` 直接向 Service 层暴露 ORM Models。
* [ ] **发现**: `RuleRepository` 内部混合了 DB 访问与自定义 `W-TinyLFU` 缓存逻辑。
* [ ] **发现**: `web_admin` 路由直接调用 Repository 和 Container。
* [ ] **发现**: Web 响应缺乏 Schema (Pydantic) 保护。


* [x] **系统生命周期与启动审计** [完成]
* [ ] **发现**: `main.py` (800+行) 上帝脚本。
* [ ] **发现**: `Container` 职责不纯。
* [ ] **发现**: 日志系统过度设计。
* [ ] **发现**: 事件总线跨层调用。


* [x] **过滤器与 IO 审计** [完成]
* [ ] **发现**: `FilterMiddleware` 硬编码过滤器。
* [ ] **发现**: IO 职责越权。
* [ ] **发现**: 网络请求碎片化。


* [x] **中间件与分层审计** [完成]
* [ ] **发现**: `SenderMiddleware` 职责过重。
* [ ] **发现**: 绕过 DI 获取 Client。
* [ ] **发现**: `MessageContext` 不规范。


* [x] **模型与持久化审计** [完成]
* [x] 审查 `middlewares/dedup.py` 和 `filters/` 中的性能瓶颈。
* [x] 分析 `unified_forward_manager.py` 的逻辑。



---

## 阶段 2：基础设施抢修与死代码清除 (P0 - Critical) [已完成]

*目标：消除循环依赖，清理物理目录，修复启动流程，建立最基础的架构规范。*

* [x] **20260125_Core_Infrastructure_Cleanup_Phase2 [已完成]**

* [x] **物理目录歼灭战 [P0]**
* [x] **删除** `managers/` 及其目录下所有 Legacy 代码。
* [x] **删除** `zhuanfaji/` 冗余统计目录。
* [x] **删除** `ufb/` 目录，消除磁盘上的孤立 JSON 存储（合并至 `remote_config_sync`）。


* [x] **解耦与依赖治理 [P0]**
* [x] 彻底解决 **循环依赖**:
* [x] 重构 `core/container.py` 以支持 Provider 模式或 Setter 注入。
* [x] 将 `Settings.load_dynamic_config` 逻辑外迁至专门的初始化器。


* [x] **核心链路解耦**:
* [x] **重构 `core/event_bus.py**`: 打破循环依赖，移除对 `web_admin` 控制器的任何直接引用。




* [x] **引导程序重构 (`main.py` 解耦) [P0]**
* [x] 创建 `core/bootstrap.py` 负责应用启动序列。
* [x] 创建 `core/lifecycle.py` 负责统一的生命周期钩子（Startup/Cleanup）。
* [x] 将 **Cron 逻辑** 从 `main.py` 移至专用的 `scheduler/cron_service.py`。


* [x] **核心组件合并与服务化**
* [x] 将 `StateManager` 逻辑并入 `services/state_service.py`。
* [x] 规范化 `ai/` 集成（提供者 -> 服务 -> 接口）。(Pre-existing)
* [x] 统一数据库初始化和访问（`core/database.py` vs `db/`）。
* [x] **基础设施池化 [P1]**: 在 `Container` 中初始化全局 `aiohttp.ClientSession` 连接池，供 AI、RSS 及网络服务复用。
* [x] **合并数据库管理器**: 审查并清理 `utils/db/` 下冗余的 `database_manager.py` 与 `db_manager.py`，统一归口至 `core/database.py`。



---

## 阶段 3：数据安全与核心层纯净化 (P0 - Critical)

*目标：严禁 ORM 模型泄露，强制 DTO 转换，拆分上帝类。*

* [x] **Repository 纯净化与强制使用 [P0]** (已完成：强制返回 DTO，屏蔽直接 ORM 泄露)
* [x] **定义 DTO/Schemas 层**: 使用 Pydantic (已全量强制).
* [x] **重构 `RuleRepository`**: 确保返回 `RuleDTO`、`ChatDTO`（领域模型）而非 `ForwardRule` ORM 对象.
* [x] **重构 `UserRepository`**: 确保返回 `UserDTO` 而非 `User` ORM 对象.
* [x] **重构 `RuleManagementService`**: 分层完成，Facade/Logic/CRUD 分离.
* [x] **层级解耦**: 严禁 Repository 直接调用 Service，Utils 纯净化中.


* [x] **数据库持久化治理 [P0]**
* [x] **引入 Alembic** (已初始化并生成首个迁移).
* [x] **拆分模型层**: 将 `models/models.py` 拆分为 `models/rule.py`, `models/chat.py`, `models/user.py` 等。(已修复 `ForwardRule` 字段缺失问题)
* [x] **集成测试修复**: 通道流水线 (Pipeline) 及 转发逻辑 (Sender) 端到端测试全部通过。


* [x] **上帝文件拆分 (按职责完整性) [P0/P1]**
* [x] **拆解 `command_handlers.py**` (2445行) [P0]:
* [x] 分解为：媒体指令、规则指令、系统管理指令、管理员专属指令。
* [x] **核心审计**: 移除 Handler 内部的所有 `session.execute` 调用，强制通过 `RuleManagementService` 执行业务。


* [x] **拆解 `rule_management_service.py**` (72KB):
* [x] 分离为 `RuleCRUDService`、`RuleLogicService`、`RuleConfigService` (Facade/Logic/CRUD).


* [x] **`utils/helpers/common.py` (716 行) [P0]**:
* [x] 业务逻辑全量下沉进入相关 Service；彻底移除 `is_admin` 等函数中的越权 DB 操作 (已重构，委托给 UserService/RuleFilterService).





---

## 阶段 4：服务层重构与 Utils 禁鲜令 (P1 - High)

*目标：将分散在 Utils 的逻辑收归 Service，建立标准化的业务层。*

* [x] **Utils 层业务逻辑歼灭战**
* [x] **解耦数据库**: 彻底移除 `utils/processing/` (如 `smart_dedup.py`, `batch_processor.py`) 对 `sqlalchemy` 的直接引用，通过 Repository 注入。(已迁移至 `dedup_service` 和 `task_service`)
* [x] **业务下沉**: 将 `utils/processing/message_task_manager.py` 迁移至 `services/task_service.py`。
* [x] **队列服务化**: 将 `utils/processing/forward_queue.py` 升级为 `services/queue_service.py`。
* [x] **搜索系统**: 将 `utils/helpers/search_system.py` 升级为 `services/search_service.py`，隔离远程与本地搜索 Provider。


* [x] **目录结构标准化 (大一统)**
* [x] `utils/db/` -> `repositories/`: 彻底移除混合在 utils 中的 DB 操作。
* [x] `utils/network/` -> `services/network/`: 网络请求逻辑升级为服务。
* [x] `utils/helpers/` -> `core/helpers/`: 真正通用的纯函数。
* [x] `config/` (root) -> `core/config/`: 消除根目录冗余。


* [ ] **Service 与 Util 领域重划**
* [x] **`controllers/menu_controller.py` (上帝类治理)**: 业务逻辑剥离至 `services/menu_service.py` (及 `RuleManagementService`, `SessionService`)。
* [x] **`filters/` 逻辑大清洗**:
* [x] `rss_filter.py`: I/O 逻辑移至 `services/rss_service.py`，移除过滤器内部的媒体下载逻辑。
* [x] `ai_filter.py`: 预处理移至 `media_service`，实现 Base64 处理的流式化/熔断保护。
* [x] **实现全动态过滤链 [P1]**: 将 `FilterMiddleware` 改为完全由 `FilterChainFactory` 驱动，根据数据库规则动态组装过滤器，废除硬编码列表。
  * [x] **验证**: 已通过 `tests/integration/test_dynamic_filter_chain.py` 验证动态加载逻辑。
  * [x] **遗留测试修复**: `tests/integration/test_pipeline_flow.py` 需适配新的 Factory 模式。 (已修复)

* [x] **RSS 模块归口统一 (`rss/`)**
* [x] **整合**: 核心逻辑移至 `services/rss_service.py`；路由移至 `web_admin`；删除冗余的 `rss/` 独立目录 (确认已移除)。



---

- [x] **Phase 5：稳定性、异步合规与静默失败治理 (P1 - High)**
*目标：解决系统不稳定的根源，统一异步标准，强化错误处理。*

* [x] **静默失败全域歼灭战 [P0]** (已完成)
    - [x] **Utils 审计**: 扫描并修复 `repositories/`, `services/` 中的所有裸 `except:` 捕获。
    - [x] 修复 `rule_repo.py`, `config_service.py`, `rss_service.py`, `db_sharding.py` 中的 Bare Exception。
    - [x] 审查 `dedup_service.py`, `worker_service.py` 中的日志模式。

* [x] **阻塞 I/O 清理与异步合规性 [P1]**
    - [x] **BatchProcessor 修复**: 将 `get_event_loop` 升级为 `get_running_loop`。
    - [x] **彻底替换 requests**: 全量迁移至 `httpx` 或 `aiohttp`。
    - [x] **Web 自引用修复**: 修复 `fastapi_app.py` 中对 `/readyz` 的配置自引用，统一注入 `settings`。
    - [x] **日志推送优化**: 重构子系统为异步。

* [x] **会话 (Session) 架构重构 [P1]**
    - [x] **移动 `SessionManager`**: 移至 `services/session_service.py`。
    - [x] **解耦处理链**: 确保 Handlers 仅通过 `SessionService` 交互。
    - [x] **系统自愈**: 实现 `ensure_sessions_ok` 影子备份与自愈逻辑。

* [x] **守护任务全量异步化**
    - [x] **合并守卫逻辑**: 废除 `MaintenanceService` 和 `DatabaseMonitor` 中的 `threading.Thread`，合并至异步 `GuardService`。
    - [x] **系统日志架构清洗 [P1]**: 移除 `log_config.py` 中的非标准日志本地化逻辑，回归标准结构化输出。
    - [x] **统一调度**: 在 `GuardService` 中合并 Temp Clean, Memory Guard。



---

## 阶段 6：Web Admin 与表现层重构 (P1/P2)

*目标：标准化 API 接口，拆分庞大的路由文件。*

* [x] **Web 路由器拆解 (`web_admin/routers/`) [P1]**
* [x] **拆解 `system_router.py` (1023 行)**: 提取 `log_router.py`, `maintain_router.py`, `stats_router.py`。
* [x] **拆解 `rule_router.py` (529 行)**: 提取 DTO 映射逻辑至 `RuleDTOMapper`。
* [x] **API 现代化**: 移除 `fastapi_app.py` 中的剩余 API。


* [x] **表现层纯净化 [P2]**
* [x] 为所有路由引入 `ResponseSchema`，标准化 JSON 返回结构。
* [x] 撤销路由对 `Container` 的直接访问，改用 `Depends` 注入。
* [x] **安全与认证**: 移除 `/logout` 等路由内的手动认证，统一通过 `authentication_service`。


* [x] **Handler 与 UI 拆分**
* [x] **`handlers/button/callback/callback_handlers.py`**: 垂直拆分为 `RuleCallback`, `PageCallback` 等。
* [x] **`ui/menu_renderer.py`**: 细化为多个专用渲染器。



---

## 阶段 7：高性能算法与资源优化 (P2 - Optimization) [Done]

*目标：提升系统上限，降低资源占用，优化核心算法。*

* [x] **核心算法优化**
* [x] **去重引擎**: 优化 `bloom/`，重构 `dedup.py` (Shim & Imports Fixed)。
* [x] **过滤器流水线 2.0**: AST-like 执行计划，支持并行 Filter 执行；增加 Result Caching (FilterChainFactory 2.0)。
* [x] **调度引擎升级**: 引入优先级队列 (Priority Queue)，实现动态 Worker 池 (Dynamic Concurrency implemented in WorkerService)。


* [x] **低占用优化 (Low Consumption)**
* [x] **全局单例惰性化**: `repositories/` 和 `services/` 采用 `get_service()` 惰性加载 (Cached Properties)。
* [x] **AI 模块惰性化**: 移除 `ai/__init__.py` 的顶层暴力导入，改为按需加载。
* [x] **日志自动归档**: 实现 Rolling 更新与自动清理 (Core Logging)。


* [x] **数据层极致性能**
* [x] **数据库连接池调优**: 针对 SQLite WAL 优化，区分读/写连接池 (Models/Base Split).
* [x] **统一缓存层**: 建立 `services/cache_service.py`，实现防击穿逻辑 (Anti-Stampede).
* [x] **轻量级去重索引**: 将布隆过滤器迁移到位数组实现 (Bytearray implemented in `core.algorithms.bloom_filter`).


* [x] **网络与并发稳定性**
* [x] **Telethon 客户端池**: 实现 Scale Out 复用池 (`services/network/client_pool.py`).
* [x] **全局限流器**: 实现基于令牌桶/漏桶的精确限流 (`services/network/rate_limiter.py`).



---

## 阶段 8：工程卓越、测试与文档 (P2 - Long Term)

*目标：完善基础设施，确保长期可维护性。*

* [ ] **测试工程化 2.0**
* [x] **架构测试**: 编写脚本强制检查架构分层违规 (已实现 `.agent/skills/local-ci/scripts/arch_guard.py`)。
* [x] **Fuzz Testing**: 引入 `hypothesis` 对 Filter/Parser 进行测试 (已实现 `tests/fuzz/`).
* [x] **性能门禁库**: 在 CI 中实施资源边界检查 (已实现 `core.helpers.resource_gate`).


* [x] **标准化与合规性自检**
* [x] **配置审计**: 全项目清除 `os.getenv`，强制走 `core.config.settings` (已完成：全量覆盖)。
* [x] **ORM 泄露审计**: 建立脚本硬性检查 Service 返回值 (已实现 `scripts/orm_leak_scanner.py`)。
* [x] **死代码分析**: 使用 `vulture` 扫描并清理 (已于 2026-01-31 完成)。
* [x] **类型提示**: 核心模块 100% 类型覆盖 (已于 2026-01-31 完成)。


* [x] **部署与智能休眠**
* [x] **智能休眠**: 负载驱动唤醒，空转熔断机制 (已实现 `core.helpers.sleep_manager`并绑定墓碑机制)。
* [x] **SQLite 并发可靠性**: 优化参数 (已在 `core/database.py` 中启用 WAL 及连接池优化)，标准化存储路径。


* [ ] **文档编制**
* [x] 更新 `docs/tree.md` (已于 2026-01-29 更新)。
* [x] 更新架构图 (已创建 `docs/architecture_diagram.mermaid`).


* [x] **重构验证**
* [x] 确保 `check_completeness` 通过 (Phase 8 Exec Report 已验证)。
* [x] 重构前后性能基准测试 (已集成资源门禁与监控).


---

## 阶段 9：安全加固与审计体系 (P1 - High)

*目标：强化输入验证，标准化机密管理，通过 AOP 指令实现操作可追溯。*

* [ ] **审计服务 AOP 化 [P1]**
    - [x] 封装 `@audit_log` 装饰器，自动记录敏感 Service 方法（如 `RuleService.delete`, `UserService.update`）的执行人、参数及结果。
    - [x] 实现审计日志的异步非阻塞写入，确保审计逻辑不拖慢业务。
* [x] **机密与配置加固**
    - [x] 彻底迁移至 `pydantic-settings`，实现环境变量的自动验证与类型强制转换。
    - [x] 敏感信息（Token, Key）在 Web 端返回时强制进行脱敏处理。
* [ ] **网络安全隔离**
    - [x] 为 Web Admin 引入基于 IP 的访问频率限制（Rate Limiting）。
    - [x] 实现针对 Telegram Webhook（如果启用）的签名校验 (**N/A**: 当前使用 Telethon MTProto 协议，无需 Webhook).


---

## 阶段 10：AI 管线、媒体处理与容错 (P1 - High)

*目标：优化大流量下的 AI 处理效率，增强媒体传输的鲁棒性。*

* [x] **AI 提供者 Circuit Breaker [P1]**
    - [x] 为所有 AI Provider (Gemini, OpenAI, DeepSeek) 集成熔断器 (Implemented `CircuitBreakerProxy` in `ai/__init__.py`).
    - [x] 当上游 API 超时或报错频率过高时，自动降级至本地规则匹配或报错通知.
* [x] **媒体管线流式化**
    - [x] 重构 `AIFilter` 的图片处理逻辑，支持流式读取，避免将多张高清图同时载入内存导致的 OOM (Updated `AIMediaProcessor` with Resize & Streaming).
    - [x] 实现 `MediaHydrationService`，统一管理媒体文件的“已下载、待下载、清理中”三态.
* [x] **智能重试机制 (Smart Retry)**
    - [x] 为媒体转发实现基于指数退避算法（Exponential Backoff）的自动重试 (Implemented `SmartRetryManager` in `sender.py`).
    - [x] 区分“业务冲突（400）”与“网络波动（503）”，避免无效重试.


---

## 阶段 11：可观测性、监控与健康检查 (P2 - Medium)

*目标：从“黑盒运行”转变为“透明观测”。*

* [x] **核心指标导出 (Metrics System)**
    - [x] 集成 `prometheus_client`，导出转发成功率、API 响应耗时、连接池占用率等核心指标。
    - [x] 在 Web 管理后台增加实时的 Prometheus 走势图视图 (Backend endpoint `/metrics` enabled for Prometheus/Grafana integration).
* [x] **健康检查增强**
    - [x] 细化 `/healthz` 接口，不仅返回系统状态，还包含：
        - 数据库连接可用性。
        - Telegram Client 会话存活状态。
        - 磁盘空间（TEMP_DIR）剩余报警。
* [x] **分布式追踪 (Trace ID)**
    - [x] 在 `MessageContext` 中全链路携带 `correlation_id`，确保从监听到过滤、最终发送的日志可以通过 ID 一键聚合。


---

## 阶段 12：工程品质、工作空间治理与 CI (P2 - Medium)

*目标：维护项目整洁度，提升开发者的“心智负担”降低。*

* [x] **工作空间洁癖治理 [P2]** (Established `data/db`, `data/sessions`, `data/backups` and cleaned root)
    - [x] 强化 `workspace-hygiene` 脚本，定期自动清理根目录下的 `.log`, `.tmp`, `.json` 冗余。
    - [x] 标准化 `data/` 目录：`data/db/` (数据库), `data/sessions/` (会话), `data/backups/` (备份)。
* [x] **CI 与架构门禁 [P2]** (Implemented `scripts/ops/arch_guard.py` with AST checks)
    - [x] 编写 `scripts/arch_guard.py`，利用抽象语法树分析禁止层级违规（如 Service 反向依赖 UI）。
    - [ ] 实现单元测试覆盖率门禁，核心逻辑（Rule, Filter）覆盖率必须 > 80%。 (Filters currently ~55%, test coverage significantly improved)
* [x] **维护脚本整理** (Organized into `scripts/dev/` and `scripts/ops/`)
    - [x] 统一 `scripts/` 下的重复工具，将其分类为 `dev/` (开发辅助) 和 `ops/` (线上运维)。
    - [x] 移除所有历史遗留的 `temp_*.py` 脚本。


---

## 阶段 13：极致性能剪枝 (P2/P3 - Long Term)

*目标：在保证功能完整的前提下，压榨每一分内存和 CPU。*

* [x] **惰性加载深化** (Applied to Gemini, OpenAI, Claude providers)
    - [x] 实现针对 AI 库（如 `google-generativeai`）的 `LazyImport` 包装，仅在真正命中 AI 规则时才触发 Python 包载入。
    - [x] 深化按需加载：创建标准 `LazyImport` 工具 (`core.helpers.lazy_import`) 并扩展应用至 `DuckDB`, `PIL`, `Pandas`, `Anthropic`, `OpenAI` 等重型依赖。
* [x] **SQLite 极致调优** (Verified in `core/db_factory.py` with WAL, NORMAL sync, and mmap)
    - [x] 针对高并发读写，开启 SQLite 的 `WAL` 模式并优化 `synchronous` 和 `mmap_size` 参数。
* [x] **垃圾回收控制 (GC Tuning)** (Implemented in `WorkerService.adaptive_sleep`)
    - [x] 在 `WorkerService` 高频任务结束后手动触发 `gc.collect()` 的软清理，确保存储碎片及时释放。