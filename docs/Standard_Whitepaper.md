# TG ONE 工程标准白皮书 (Engineering Standard Whitepaper)

> 版本: 2026.1 (Architecture Refactor Edition)
> 适用范围: 全项目 (Core, Services, Utils, Tests, Web Admin)
> 
> 本文档基于 2026年1月 深度重构与架构优化的成果总结而成。所有后续开发任务、代码审查(Code Review)及自动化检测均须以此为最高准则。

## 1. 核心架构原则 (Core Architecture Principles)

### 1.1 极致惰性执行 (Ultra-Lazy Execution)
*   **定义**: 凡是能推迟初始化的，必须推迟到第一次被调用时。
*   **红线**:
    *   **禁止** 模块级顶层实例化 (e.g. `service = Service()` or `db = Database()`)。必须封装在 `get_instance()` 或 `@lru_cache` 工厂函数中。
    *   **禁止** `__init__` 中执行重 IO 操作（如连接 DB、加载 AI 模型、读取大文件）。必须后置到 `start()` 或首次 `call`。
    *   Web Admin 的 Router 依赖必须使用 `Depends(get_service)`，严禁直接 `from ... import service_instance`。

### 1.2 架构正交与分层 (Orthogonality & Layering)
*   **定义**: 严格遵守 `Controller -> Service -> Repository -> Data Model` 的调用链路，禁止跨层或反向依赖。
*   **红线**:
    *   **Utils 纯净性**: `utils/` 目录 **严禁** 包含业务状态或直接引用 `sqlalchemy`、`Select` 等数据库原语。Utils 只能是纯函数。
    *   **Service 职责**: 业务逻辑必须且只能在 `services/` 中。禁止 Handler 或 Utils 处理业务。
    *   **Repository 纯度**: Repository 必须返回 Pydantic Domain Model 或 DTO。**严禁** 将 SQLAlchemy ORM 对象（带 Session 状态）泄漏给 Service 层。
    *   **Handler 纯净化 (Handler Purity)**: `handlers/` 目录中的文件 **严禁** 直接导入 `sqlalchemy` 或 `models.models`。所有数据操作必须委托给 Repository，业务逻辑（如规则同步、复杂更新）必须委托给 Service。
 
### 1.3 高内聚与低耦合 (Cohesion & Coupling)
*   **定义**: 模块拆分应基于“业务领域完整性”，而非简单的代码行数。
*   **红线**:
    *   禁止仅为了减少行数而强行拆分文件（如 `part1.py`, `part2.py`）。
    *   相关联的逻辑（如去重策略与指纹计算）应组织在同一包下的不同模块中，对外暴露统一 Facade。
    *   **上帝文件治理**: 单文件超过 1000 行且包含多个不相关业务（如同时处理 Auth 和 Forward）时，必须按业务领域垂直切分。
### 1.4 智能休眠与极致能效 (Intelligent Dormancy & Efficiency)
*   **有效负载驱动 (Payload-Driven)**: 
    *   **定义**: 系统唤醒必须由“有效业务产生”驱动，而非“无意义流量”。
    *   **规范**: 若 Filter 过滤了所有消息，消费者（Queue, DB）保持挂起。仅当有 Payload 入队时才申请资源。
*   **零开销待机 (Zero-Overhead Standby)**:
    *   任务队列空闲 5 分钟后，必须触发 `System.suspend()`。
    *   **动作**: 缩减 DB 连接池至 0/1 连接，**卸载 AI/NLP 模型内存对象**，暂停轮询 Loop。

## 2. 代码与工程规范 (Coding & Engineering Standards)

### 2.1 异步与并发安全 (Async & Concurrency)
*   **IO 密集型**: 所有涉及网络、磁盘、数据库的操作 **必须** 是 `async/await` 的。
*   **Windows IO 安全**: 
    *   严禁在 Windows 环境下对 `asyncio.get_running_loop().run_in_executor` 进行 Mock（会导致系统死锁）。
    *   测试中应使用 `patch_io_methods` 拦截底层 IO，而非 Mock 线程池。
*   **锁机制**: 并发修改共享资源（如去重缓存、计数器）必须使用 `asyncio.Lock` 或 Redis 分布式锁。

### 2.2 错误处理与可观测性 (Error Handling & Observability)
*   **禁止静默失败**: 
    *   **严禁** 全局范围的 `except: pass`。
    *   **严禁** `except Exception as e: logger.error(e)` 后不抛出也不处理（吞没异常），导致上层误以为成功。
    *   必须使用自定义异常体系（如 `ServiceException`, `ValidationException`）。
*   **标准错误码**: 使用 `core/errors.py` 定义的统一错误码 (e.g. `ERR_RATE_LIMIT`)，禁止硬编码字符串匹配。
*   **日志规范**: 关键业务节点（启动、任务开始、任务结束、异常）必须有 Info/Error 级别日志，且包含 TraceID 或 TaskID。
*   **标准收口**: 所有日志记录必须通过 `core.logging` 统一入口，禁止使用 `print` 或原始 `logging` 模块。

### 2.3 数据库交互 (Database Interaction)
*   **Repository 模式**: 所有 SQL/ORM 操作必须封装在 `repositories/` 中。Service 层禁止出现 `session.execute()`。
*   **Session 管理**: 
    *   遵循 "Session per Request" 或 "Session per Task" 模式。
    *   严禁保存 Session 对象到全局变量或长生命周期对象中。
    *   必须使用 `async with session_scope():` 或 `Depends(get_db)` 确保 Session 正确关闭。
    *   **通用设置接口**: 所有针对 ForwardRule 的简单/复合设置更新必须通过 `RuleManagementService.update_rule_setting_generic`。此接口强制收口 `RuleSync` 逻辑，确保配置更改能一致地传播到相关规则。

### 2.4 标准化与统一 (Standardization & Unification)
*   **配置统一**: 全项目强制使用 `core.config.Settings`。**严禁** 使用 `os.getenv` 散点调用，**废除** `utils/core/env_config.py`。
*   **日志统一**: 废除 `utils/core/logger_utils.py`, `utils/core/log_config.py`，统一收口至 `core/logging.py`。
*   **工具收敛**: 
    *   数据库维护工具统一至 `services/db_maintenance_service.py`。
    *   通用逻辑（如 Search, Sender）必须“服务化” (`services/search_service.py`, `services/sender_service.py`)，**严禁** 作为胖脚本留在 `utils/` 中。
    *   Scheduler 任务必须统一，移除冗余的 `scheduler/chat_updater.py`。

## 3. 测试与质量保障 (QA & Testing)

### 3.1 测试策略
*   **单元测试**: 核心 Service 和 Util 必须有单元测试覆盖（Coverage > 80%）。
*   **Mock 规范**: 
    *   对于 Loop 中的 Mock 对象，必须设置 `mock.reset_mock()` 或限制 `mock_calls` 历史记录，防止内存爆炸 (RAM Leak)。
*   **无副作用**: 测试用例执行完毕后，必须清理产生的文件、数据库记录和全局状态。

## 4. 维护与演进 (Maintenance & Evolution)

*   **死代码清理**: 
    *   根目录下禁止存放 `test_fix.py`, `debug.py` 等临时脚本，用完即删。
    *   不再使用的旧代码路径必须及时标记 `@deprecated` 或直接移除。
*   **文档同步**: 
    *   每次架构变更后，必须同步更新 `todo.md`, `process.md` 和本文档。
    *   `docs/tree.md` 必须反映真实的文件结构。

---
> **执行力说明**: 
> AI Assistant 在执行任何任务前，应快速自检是否违反上述红线。
> 项目维护者(Maintainer) 应定期运行静态分析工具(`vulture`, `mypy`) 验证规范执行情况。
