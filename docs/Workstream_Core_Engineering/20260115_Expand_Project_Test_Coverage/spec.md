# Test Extension Specification

## 1. 现状分析
当前测试主要集中在 `services/` 层。
- **Service 层**: 覆盖率良好 (Analytics, Auth, Audit, Dedup, Rule)。
- **Repository 层**: 缺乏独立的单元测试（目前通过 Service 测试间接覆盖）。
- **Handler 层**: 单元测试不完整，特别是 Telegram 处理逻辑。
- **Router 层**: 缺乏 Web 路由的集成测试。

## 2. 测试架构设计
遵循 `pytest` 框架和 `conftest.py` 已有的延迟加载策略。

### 2.1 Repository 测试
- **目标**: 验证 SQL 语句和数据映射。
- **技术栈**: `pytest-asyncio`, `aiosqlite` (内存版)。
- **位置**: `tests/unit/repositories/`。

### 2.2 Handler 测试
- **目标**: 逻辑验证，Mock 外部 Telegram API。
- **技术栈**: `unittest.mock`, `pytest-asyncio`。
- **位置**: `tests/unit/handlers/`。

### 2.3 Router 测试 (Phase 1 ✅)
- **目标**: 接口验证，包括 Auth 校验和异常处理。
- **技术栈**: `httpx` (AsyncClient), `FastAPI` (TestClient 异步模式)。
- **位置**: `tests/integration/`。
- **已完成**: `AuthRouter`, `RuleRouter`, `UserRouter`, `SystemRouter`。

### 2.4 Middleware 测试 (Phase 2)
- **目标**: 验证请求/响应拦截逻辑、CSRF 防护、IP 白名单、Trace ID 注入。
- **技术栈**: `httpx` (AsyncClient), Mock Request/Response。
- **位置**: `tests/unit/middlewares/`。
- **关键测试点**:
  - TraceMiddleware: 验证 Trace ID 生成和传播。
  - IPGuardMiddleware: 验证 IP 白名单和黑名单逻辑。
  - CSRFMiddleware: 验证 Token 生成、验证和白名单路径。

### 2.5 Security Module 测试 (Phase 2)
- **目标**: 验证安全组件的正确性和健壮性。
- **技术栈**: `pytest`, `unittest.mock`。
- **位置**: `tests/unit/security/`。
- **关键测试点**:
  - RateLimiter: 验证限流、锁定、解锁逻辑。
  - PasswordValidator: 验证密码强度检查规则。
  - JWT Token: 验证 Token 生成、验证、过期处理。
  - ActiveSessionService: 验证会话管理和旋转机制。

### 2.6 Filter & Listener 测试 (Phase 2)
- **目标**: 验证消息过滤和事件监听逻辑。
- **技术栈**: `pytest-asyncio`, Mock Telegram Event。
- **位置**: `tests/unit/filters/`, `tests/unit/listeners/`。
- **关键测试点**:
  - 消息过滤器: 验证关键词匹配、正则表达式、媒体类型过滤。
  - 事件监听器: 验证事件触发和处理逻辑。

### 2.7 Utils 测试 (Phase 2 - Critical)
- **目标**: 验证核心工具类的正确性和边界条件。
- **技术栈**: `pytest`, `pytest-asyncio`。
- **位置**: `tests/unit/utils/`。
- **关键模块**:
  - **db_operations.py**: 数据库操作封装，验证 CRUD 和事务处理。
  - **forward_recorder.py**: 转发记录器，验证文件写入和格式化。
  - **unified_sender.py**: 统一发送器，验证限流和重试逻辑。
  - **id_utils.py**: ID 工具，验证标准化和候选 ID 生成。
  - **realtime_stats.py**: 实时统计，验证缓存和聚合逻辑。
  - **smart_dedup.py**: 智能去重，验证 Bloom Filter、SimHash、HLL。
  - **ac_automaton.py**: AC 自动机，验证多模式匹配。
  - **rate_limiter_pool.py**: 限流池，验证多实例管理。

### 2.8 Integration Tests (Phase 2 - E2E)
- **目标**: 验证完整业务流程的端到端正确性。
- **技术栈**: `pytest-asyncio`, `httpx`, Mock Telegram Client。
- **位置**: `tests/integration/`。
- **关键场景**:
  - **消息转发流程**: 从接收消息到转发完成的完整链路。
  - **规则 CRUD + 媒体过滤**: 创建规则、设置媒体过滤条件、验证转发逻辑。
  - **用户认证和会话管理**: 注册、登录、2FA、Token 刷新、登出。
  - **统计收集和报告**: 消息统计、性能指标、实时数据展示。

## 3. 质量标准

### 3.1 Phase 1 标准 (已达成 ✅)
- 核心 Repository 必测。
- 关键 Handler 逻辑必测。
- 所有 API Endpoint 需有正向及负向测试各至少 1 例。
- **严禁**：在测试中产生持久化磁盘文件（除非明确指定目录）。
- **目标覆盖率**: > 70% (核心模块)。

### 3.2 Phase 2 标准 (进行中)
- **中间件**: 每个中间件至少 3 个测试用例（正常、异常、边界）。
- **安全模块**: 覆盖所有安全相关逻辑，包括攻击场景模拟。
- **工具类**: 覆盖所有公共方法和边界条件。
- **E2E 测试**: 每个核心业务流程至少 1 个完整测试。
- **目标覆盖率**: > 85% (全模块)。
- **性能要求**: 单元测试 < 100ms/用例，集成测试 < 1s/用例。

### 3.3 测试隔离和清理
- 所有测试必须使用 `@pytest.mark.usefixtures("clear_data")` 确保数据隔离。
- 使用内存数据库 (`:memory:`) 或共享内存模式。
- 测试结束后自动清理所有临时文件和数据。

### 3.4 Mock 策略
- **单元测试**: 深度 Mock 所有外部依赖（数据库、网络、文件系统）。
- **集成测试**: 仅 Mock 外部服务（Telegram API），保留内部组件真实交互。
- **E2E 测试**: 最小化 Mock，尽可能使用真实组件。

## 4. 实施优先级

### P0 (Critical - Phase 2 首批)
1. Security Module Tests (安全是基础)
2. Middleware Tests (请求处理链路)
3. Utils Tests (Critical) - db_operations, forward_recorder, unified_sender

### P1 (High - Phase 2 次批)
4. Router Tests (Phase 2) - StatsRouter, SettingsRouter
5. Utils Tests (Processing) - smart_dedup, bloom_filter, ac_automaton
6. Filter & Listener Tests

### P2 (Medium - Phase 2 后续)
7. Utils Tests (Network) - rate_limiter_pool, flood_wait_handler
8. Integration Tests (E2E) - 完整业务流程

## 5. 持续改进
- 每周运行覆盖率报告，识别低覆盖区域。
- 对新增代码强制要求配套测试（CI/CD 集成）。
- 定期审查和重构测试代码，保持可维护性。
