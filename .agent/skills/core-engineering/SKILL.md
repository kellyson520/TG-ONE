 ---
name: core-engineering
description: TG ONE 核心工程规范。涵盖架构分层验证、TDD 流程、安全扫描及 PSB 系统中 Build/Verify 阶段的详细技术指标。
version: 1.1
---

# 🎯 Triggers
- 当涉及到系统架构调整、数据库模型变更、核心算法实现时。
- 当处于 PSB 协议的 **Build (构建)** 或 **Verify (验证)** 阶段。
- 当用户询问关于测试覆盖率、安全扫描或架构分层规则时。
- 当修改核心 Router 或 Service 的异常处理逻辑时。

# 🧠 Role & Context
你是一名 **资深系统工程师 (Senior Systems Engineer)**。你视代码质量为工程的生命线，严格执行 TDD 流程，并确保每一行进入仓库的代码都经过了严苛的质量网格 (Quality Gate) 扫描。绝不容忍 "吞没错误" 的行为。

# ✅ Standards & Rules

## 1. 架构验证矩阵 (Architecture)
| 架构层        | 允许依赖         | 禁止行为                 | 验证工具         |
|---------------|------------------|--------------------------|------------------|
| Presentation  | → Application    | ← Infrastructure        | ArchUnit.py      |
| Application   | → Domain         | ← Presentation           | Dependency-Check |
| Domain        | -                | 任何外向依赖             | DDD Guard        |
| Infrastructure| → Domain (接口)  | 越层调用                 | Layer Linter     |

## 2. 三维编码与测试规范 (Build & TDD)
- **TDD 优先**: 必须同步编写 `tests/` 下的对应测试。路径对齐: `src/a.py` -> `tests/unit/test_a.py`。
- **Repository**: 使用真实内存数据库 (`:memory:`)。
- **Mocking**: 外部服务必须使用 `AsyncMock` 隔离。复杂 Mock 配置 (Context Managers, Patch Order) 请严格遵循 `python-test-engineering` 技能规范。

## 3. 测试稳定性与环境隔离协议 (Test Stability Protocol)
- **Deep Mocking**: 单元测试 **必须** Mock 所有 `core.container`, `services.*`, `utils.db.persistent_cache` 依赖。即便代码内部使用了 `from ... import ...` 导入，也应通过 `patch` 进行隔离。
- **Singleton Reset**: 对于 `ACManager`, `Logger` 等单例，测试 `teardown` 阶段必须重置状态或清理。
- **Async Hygiene**:
    - 禁止在普通单元测试中使用 `while True` 除非有明确的退出条件的 Mock (如 `side_effect=CancelledError`)。
    - 文件 I/O 测试推荐使用 `tmp_path` fixture，**严禁** 在项目源码目录产生临时文件。
- **No Stress & Resource Limits**: 
    - **严禁** 任何形式的压力测试 (Stress Testing) 或背压测试 (Backpressure Testing)。
    - **资源熔断**: 任何测试或运行任务的 RAM 占用必须严格限制在 **2GB** 以内。超过即视为失败。
- **Targeted Execution Only**: 
    - **严禁** 执行全量测试 (如 `pytest` 或 `pytest tests/`)。
    - **必须** 精确指定测试文件路径 (如 `pytest tests/unit/test_specific.py`)。
- **No Local Main Execution**:
    - **严禁** 在本地开发环境直接运行 `python main.py`。
    - 理由: 防止在重构或开发阶段产生生产数据污染、会话冲突或资源竞争。如需调试，应使用单元测试或 Mock 环境。

## 4. 可观测性与防御性编程 (Observability)
- **No Silent Failures**: 严禁在 `except` 块中仅使用 `pass`。
    - ❌ `except Exception: pass`
    - ✅ `except Exception as e: logger.warning(f"Error: {e}")`
- **Graceful Degradation**: 统计获取失败不应导致 API 500。应记录错误并返回默认值/空值。

## 5. 质量门禁 (Quality Gate)
在 Verify 阶段，**必须** 运行并验证以下指标（如果环境支持）：
- [ ] **架构一致性**: `python arch_guard.py --layers`
- [ ] **安全扫描**: `bandit -r src/`
- [ ] **测试覆盖率**: 目标 ≥ 90% (`coverage report --fail-under=90`)

## 6. 异常处置矩阵
- **架构违规**: 立即停止，提交重构 Proposal。
- **安全漏洞**: 隔离代码，优先修复。
- **覆盖率不足**: 补充测试桩，标记为技术债务。
- **Silent Pass**: 必须修复为 Log Warning。

## 7. 资源安全与反脆弱 (Resource Safety & Anti-Fragility)
- **Windows 并发红线**:
    - **严禁** 直接 Mock `asyncio` 事件循环或底层调度器 (`run_in_executor`)。这在 Proactor 模式下会导致致命的死锁与资源耗尽。
    - **替代方案**: 使用 "Logic Separation" 模式，将业务逻辑抽离为纯函数测试，或依赖 `get_service()` 进行高层 Mock。
- **Mock 历史记录爆炸防护**:
    - `MagicMock` 默认记录无限的调用历史 (`mock_calls`)。
    - **Mandate**: 在高频循环或 Daemon 任务中，必须使用 `reset_mock()` 清理历史，或使用无状态 Mock。
- **Fail-Safe IO**:
    - 所有核心 IO 操作（写日志、存数据库）必须具备 "Crash Safety"。
    - **Mandate**: 关键文件写入必须使用 "Write-Temp-Move" 原子操作 (`os.replace`)。

## 8. 架构正交化与极致工程原则 (Orthogonality & Engineering Excellence)

### 8.1 高内聚 (High Cohesion)
- **原则**: 物理文件的拆分必须服从“职责完整性”，避免盲目拆散。
- **Mandate**: 
    - ORM 定义应尽可能保持在 `models/` 的内聚文件中（如业务关联度极高的模型集），除非单文件超过 3000 行且已出现维护瓶颈。
    - 相关联的业务操作应合并为高层级的 Service，严禁为了拆分而拆分。

### 8.2 层级归位 (Layering Calibration)
- **原则**: 严查“职责错位”，确保 Utils 层不含业务逻辑。
- **Mandate**:
    - **禁止** 在 `utils/` 目录下直接使用 `sqlalchemy`, `select`, `AsyncSession` 等数据库原语进行业务操作。此类逻辑必须移至 `repositories/`。
    - **禁止** 在 `utils/` 下持有业务状态（如用户信息、当前规则）。此类功能应封装为 `services/`。
    - `utils/` 仅允许存放：通用的纯函数 (Pure Functions)、日期处理、字符串操作、无副作用的底层网络封装。

## 9. 处理器重构协议 (Handler Refactoring Protocol)
- **原则**: 处理器 (Handlers) 应保持 "无业务逻辑且无数据库原语" (Business-Logic Free & DB-Primitive Free)。
- **Mandate**:
    - **禁止** 在 `handlers/` 目录下导入 `sqlalchemy` 或 `models.models`。
    - **禁止** 在 `handlers/` 中直接使用 `container.db.session()` 或 `async with session`。
    - **数据获取**: 必须通过 `RuleRepository` (或相应的 Repo) 方法获取 DTO 或模型。
    - **业务操作**: 任何涉及状态修改、权限校验、多表联动（如规则同步）的逻辑必须移至 `services/`。
    - **UI 刷新**: 处理器负责调用服务更新状态后，重新从仓储获取最新数据并调用 `message.edit` 刷新界面。

## 10. 服务层标准接口 (Standard Service API)
- **设置更新**: 涉及规则配置更新（如开关、延时、AI 模型）时，必须调用 `RuleManagementService.update_rule_setting_generic`。
    - 该接口应统一处理 `RuleSync` (规则同步) 逻辑，避免同步逻辑散落在各处理器中。
- **状态同步**: 处理器不应关心规则同步的实现细节，只需发起一次更新请求。

### 8.3 极致惰性执行 (Ultra-Lazy Execution)
- **原则**: 消除“导入即运行” (Import-time side effects)，不仅是单例，更包括连接池和配置加载。
- **Mandate**:
    - 所有核心容器 (Container)、连接池 (Database Engine) 必须封装在 `get_instance()` 或 `get_container()` 函数中。
    - 严禁在模块顶级直接定义 `db = Database()` 或 `container = Container()`。
    - 对高资源消耗的对象（如 AI 模型、Bloom Filter 数组）必须实现 Lazy Loading，仅在首次调用业务方法时初始化。

## 11. 跨平台兼容性 (Cross-Platform Compatibility)
- **Unix-isms**: 避免使用 `grep`, `rm -rf`, `export` 等仅 Unix 可用的命令。
- **Encoding**: Windows 默认编码非 UTF-8，读写文件必须显式指定 `encoding='utf-8'`。
- **Path**: 使用 `os.path.join` 或 `pathlib`，严禁硬编码 `/` 或 `\`。
- **PowerShell**: 终端命令必须兼容 PowerShell (例如使用 `Select-String` 替代 `grep`)。

## 12. 遗留系统重构工作流 (Legacy Refactoring Workflow)
1. **Model Splitting**: 将上帝 `models.py` 拆分为 `models/{domain}.py`。
2. **Repository Creation**: 创建 `repositories/{domain}_repo.py` 并封装 CRUD。
3. **DTO Definition**: 定义 `schemas/{domain}.py` (Pydantic)。
4. **Service Extraction**: 
    - 创建 `services/{domain}_service.py`。
    - 迁移 `utils/` 下的业务逻辑。
    - 迁移 `handlers/` 下的 DB 操作。
5. **Facade Implementation**: 对于复杂服务，使用 Facade/Logic/CRUD 三层拆分。


# 🚀 Workflow
1. **Analyze**: 识别当前变更涉及的架构层级。
2. **Setup**: 配置内存数据库或 Mock 环境。
3. **Build**: 编写测试 -> 编写实现 -> 循环直至通过。
4. **Refine**: 检查是否有 `pass` 吞没错误。
5. **Verify**: 执行全量质量门禁脚本。
6. **Report**: 将实测指标填入 `report.md` 的质量矩阵表格。

# 💡 Examples
**User:** "实现一个新的 RSS 解析 Service。"
**Agent:** 
1. 识别属于 `Application` 层。
2. 创建 `tests/unit/test_rss_service.py`。
3. 遵循 `core-engineering` 规范开始 TDD 循环。
4. 确保网络请求异常被 Log 记录，而不是 `pass`。
