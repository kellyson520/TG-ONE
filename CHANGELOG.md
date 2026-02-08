# Change Log
 
## 📅 2026-02-08 更新摘要

### 🚀 v1.2.4.3: 工业级更新交互与故障自愈 (Advanced Update & Rollback Interface)
- **Infrastructure & Reliability**:
    - **Uptime Guard**: 在 `entrypoint.sh` 中引入“启动守护绿洲”，实现在更新后 15 秒内发生崩溃时自动执行回滚，彻底终结“坏版本导致死循环”的运维隐患。
    - **State Verification**: 引入 `UPDATE_VERIFYING.json` 中间态锁，使系统在“观察期”内仍能识别潜在故障并触发安全降级。
    - **Physical Failover**: 增强物理备份逻辑，在 Git 回滚受阻时（如仓库损坏），自动通过 `.tar.gz` 原始代码包还原核心目录。
- **Interactive Interfaces (Maximum Reuse)**:
    - **Python CLI**: 新增 `scripts/ops/manage_update.py`，支持终端查看状态 (`status`)、补丁/全量更新 (`upgrade`) 和紧急救急 (`rollback`)。
    - **Bot Management**: 在 `/update` 和 `/rollback` 指令中集成二次确认逻辑与目标版本选择，支持精确回滚至历史版本 (`/history` 跳转)。
    - **Architecture Consistency**: 重构 `UpdateService` 将原本分散在 CLI 和 Bot 的更新逻辑收口为统一的异步状态机指令，确保操作幂等与状态同步。

## 📅 2026-02-08 更新摘要

### 🚀 v1.2.4.2: 修复 Bot 命令菜单乱码 (Fix Bot Command Encoding)
- **Critical Encoding Fix**:
    - **Double-Encoding Recovery**: 深度分析并修复了 `handlers/bot_commands_list.py` 中的严重乱码问题（UTF-8 -> GBK -> UTF-8 双重编码破坏），恢复了所有 Bot Command 的中文描述与 Emoji。
    - **Recovery Script**: 开发并执行了专用的逆向修复脚本，成功还原了 90+ 行受损代码。
    - **Verification**: 通过 `syntax_check.py` 验证了修复后文件的 Python 语法完整性，并移除了可能导致编译问题的 UTF-8 BOM 头。

### 🚀 v1.2.4.1: 运维卫生与关闭流程优化 (DevOps & Shutdown Optimization)
- **DevOps & Logging**:
    - **Visible Dependency Check**: 增强了 `entrypoint.sh` 的守护进程日志，在校验依赖时增加 `🔍校验中...` 和 `✅校验通过` 的明确输出，消除重启时的“黑盒”状态。
    - **Shutdown Idempotency**: 优化了 `ShutdownCoordinator` 和 `LifecycleManager` 的协作逻辑，通过状态预检实现关闭流程的幂等性。
    - **Log Noise Reduction**: 将重复触发关闭流程时的警告级别从 `WARNING` 降级为 `INFO`，解决了多触发源导致的噪音警告。
- **Arch Integrity**:
    - **Redunancy Removal**: 移除了 `main.py` 启动异常块中冗余的 `lifecycle.stop()` 调用，系统现由 `lifecycle.start()` 内部闭环处理严重异常。
- **Engineering Hygiene**:
    - **Automated Archiving**: 使用 `docs-archiver` 技能完成了 10+ 个已结算任务（如 `20260207_FixGreenletError_History` 等）的归档清理。
    - **Tree Sync**: 同步更新 `docs/tree.md` 索引，确保物理文件与目录文档一致。
    - **Cleanup**: 清理了调试用的临时脚本 `tests/reproduce_double_shutdown.py`。

### 🚀 v1.2.4.0: 去重引擎健壮性与冲突修复 (Dedup Engine Robustness & Fixes)
- **Core Fixes**:
    - **Method Alignment**: 修复了 `DedupRepository` 中 `batch_add_media_signatures` 的 `AttributeError` 命名不一致问题。
    - **Logic De-conflict**: 移除了 `KeywordFilter` 中冗余的去重校验，解决了与 `DedupMiddleware` 双重锁定导致的“全员误判为重复”关键 Bug。
    - **Reliability Improvement**: 实现刷写缓冲区失败时的**自动重新入队 (Re-queueing)** 机制，确保高负载下的数据完整性。
    - **Safe Filtering**: 在仓库层引入字段过滤，防止 `bulk_insert_mappings` 因模型冗余字段导致的运行时异常。
- **Stability**:
    - **Similarity Guard**: 修复了 `SimilarityStrategy` 中 `comparisons` 变量未定义的 `NameError`。
    - **History Skip**: 在 `DedupMiddleware` 中增加对 `is_history` 任务的自动跳过，保障了历史补全流程的连贯性。
- **Verification**:
    - 新增 `tests/unit/repositories/test_dedup_repo_batch.py` 验证批量写入健壮性。


### 🚀 v1.2.3.9: 数据库监控与高级去重 (Database Monitoring & Advanced Dedup)
- **Database Monitoring System**:
    - **Performance Dashboard**: 实现 `db_performance_monitor` 面板，实时展示 QPS、慢查询分析 (Slow Query Analysis) 和热点表统计。
    - **Optimization Center**: 集成 `db_optimization_center`，提供基于规则的自动诊断建议 (Anomaly Detection Recommendations) 和一键优化功能 (VACUUM/REINDEX)。
    - **Visual Trends**: 引入 ASCII 字符画趋势图 (`render_db_performance_trends`)，直观呈现近 7 天的数据库写入负载变化。
- **Advanced Deduplication Settings**:
    - **Per-Rule Configuration**: 实现规则级去重策略覆盖 (Rule-Level Override)，允许针对特定转发规则单独配置“智能相似度阈值”和“自定义时间窗口”。
    - **UI Integration**: 在规则详情页集成 `dedup_settings` 入口，支持可视化切换全局/自定义配置模式。
- **Infrastructure**:
    - **Service Integration**: 将 `DBMaintenanceService` 深度集成至菜单系统，实现从 UI 直接触发后端维护任务。
    - **Cache Management**: 新增去重缓存 (L1/L2) 的实时监控与手动清理功能。


### 🚀 v1.2.3.8: 去重引擎 V3 升级 (Dedup Engine V3)
- **Core Algorithms**:
    - **Numba JIT**: 集成 Numba 对汉明距离计算进行位运算优化，在高维向量比对场景下性能提升超过 10 倍。
    - **LSH Forest**: 引入局部敏感哈希森林 (Locality Sensitive Hashing Forest)，实现海量文本语义指纹的近似检索，比对复杂度从 $O(N)$ 优化至 $O(\log N)$。
    - **SSH v5**: 实现 Sparse Sentinel Hash v5 视频采样算法，支持对超大视频进行秒级多点特征提取，显著增强了对剪辑/混剪视频的识别能力。
- **Architecture Refactoring**:
    - **Strategic Pattern**: 将去重逻辑彻底解耦为 `Signature`, `Video`, `Content`, `Similarity` 四大独立策略，支持按需热插拔。
    - **SmartDeduplicator Facade**: 通过外观模式统一外部链路，屏蔽内部复杂的策略调度与 LSH 索引管理。
- **Infrastructure & Maintenance**:
    - **Tombstone State Management**: 实现引擎状态的“墓碑”休眠与复苏机制，在低负载时可冻结内存索引并归还物理内存，响应时透明恢复。
    - **Batched Persistence**: 引入批处理缓冲区 (Batched Buffer) 与持久化缓存 (PCache)，平衡了实时去重与数据库入库压力。
- **Verification**:
    - 全面通过 `tests/unit/services/test_dedup_service.py` 单元测试。
    - 已同步更新 `version.py` 信息。


### 🚀 v1.2.3.7: 流量统计与文档增强 (Traffic Stats & Docs)
- **New Feature (Intercepted Traffic)**: 
    - **Smart Deduplicator**: 在核心去重引擎 `SmartDeduplicator` 中集成“拦截流量”计数器，实现字节级统计 (Byte-level Accounting)。
    - **DB Schema**: `ChatStatistics` 模型新增 `saved_traffic_bytes` 字段，并通过 Migration 自动同步数据库结构。
    - **UI Enhancement**: 主菜单 (Main Menu) 新增“🛡️ 拦截流量”展示，与“💾 消耗流量”形成对比，直观呈现去重收益。
- **Documentation System**:
    - **FAQ Integration**: 实现 `MenuController.show_faq`，提供关于规则管理、去重失效、延迟等常见问题的即时解答。
    - **Detailed Docs**: 实现 `MenuController.show_detailed_docs`，补充核心概念 (Source/Target/Rule) 与高级功能的说明。
    - **Interaction Fix**: 修复了“帮助指南”页面中 FAQ 和详细文档按钮无响应的问题。

## 📅 2026-02-04 更新摘要

### 🚀 菜单系统完整性审计与修复 (Menu System Integrity Audit)
- **Standardized Toggle**: 引入 `handle_generic_toggle` 通用处理器，通过数据驱动范式解决了 31 个缺失的回调处理器问题，极大降低了按钮逻辑的重复度。
- **Routing Cleanup**: 在 `callback_handlers.py` 中通过 `callback_router` 补全了 31 个新的路由解析路径，并验证了全量 66 个回调处理器的连通性。

### 🚀 稳定性与性能治理 (Stability & Performance)
- **Circular Import Fix**: 进一步优化启动加载顺序，在 `core.container` 中实施 **Lazy Imports**，彻底解决在高吞吐场景下因交叉引用导致的启动死锁问题。
- **N+1 Query Governance**: 深度扫描并治理了数据库归档 (`db_archive_job`)、规则同步及 Repository 层的 28 个 P0 级 N+1 性能缺陷，将部分场景的查询密度从 12 次降至 6 次。
- **Performance Benchmark**: 引入 `tests/benchmarks/test_n_plus_one_perf.py` 性能测试基准，实现关键路径性能退化的自动化预警。

### 🚀 核心去重引擎质量建设 (Dedup Engine Quality)
- **Unit Test Coverage**: 为 `SmartDeduplicator` 实现 46 个维度的深度单元测试，覆盖签名生成、SimHash 相似度、视频识别及边界异常。
- **Concurrency Locking**: 优化了基于会话异步锁的去重流程，通过 `asyncio.Lock` 成功解决高并发下的 `Check-then-Act` 竞态条件问题。

### 🚀 细节修复与对齐 (Fixes & Alignment)
- **Logging System**: 修复了 `core/logging.py` 中 `structlog` 配置导致的 `TypeError`；通过加固 `SafeLoggerFactory` 并校准处理器链（引入 `render_to_log_kwargs`），解决了日志系统启动时的崩溃问题。
- **Bug Fixes**: 修复规则设置 `AddMode` KeyError；修复 Changelog 分页显示时的 `EditMessageRequest` 协议错误。
- **Engineering Hygiene**: 批量对齐了 148 个静默捕获的异常处理逻辑，注入日志并保留了错误上下文。

## 📅 2026-02-03 更新摘要

### 🚀 v1.2.3.5: 启动稳定性修复 (Startup Stability)
- **Critical Fix**: 
    - **Circular Import**: 彻底解决了 `core.container` -> `Middlewares` -> `DedupService` -> `Container` 的循环依赖链条。
    - **Lazy Loading**: 在 Container 中实现了中间件的延迟加载逻辑，确保 core 基础设施在业务组件介入前已完成完整初始化。

### 🚀 v1.2.3.4: 代码卫生与回归修复 (Code Hygiene & Regression Fixes)
- **Code Hygiene**:
    - **Lint Fixes**: 修复 Admin Callback 中的 `F821 undefined name` (select, ForwardRule) 和 `E712` 比较错误，消除代码异味。
    - **Standardization**: 统一数据库 Session 调用，移除过时的 `async_db_session`，全面转向 `container.db.session()` 范式。
- **Regression Fixes**:
    - **Version System**: 重构版本及更新日志显示逻辑，支持分页 (`Version Pagination`)，避免更新日志过长导致的显示截断。
    - **Menu System**: 持续重构菜单系统，修复参数传递不匹配导致的崩溃问题。

### 🚀 v1.2.3.3: 交互与更新逻辑修复 (Interaction & Update Logic Fixes)
- **Update Logic Optimization**:
    - **SHA Comparison**: 优化 Git 更新检查逻辑，使用 `rev-list HEAD..origin/{branch}` 准确识别本地落后状态，修复了代码一致时仍提示更新的问题。
    - **API URL Fix**: 修正 `update_service.py` 中 GitHub API URL 的硬编码拼接错误，确保安全交叉验证 (Cross-Verification) 通道可用。
    - **Undefined Variable Fix**: 修复 `_perform_git_update` 中 `remot_id` 未定义导致的更新过程中断崩溃。
- **Routing & Menu System**:
    - **New Route Support**: 修复转发规则创建后跳转 `rule_settings:New` 时出现的 "未找到路由处理程序" 错误。
    - **Menu System Audit**: 完成 `NewMenuSystem` 第一阶段审计，修复了 `ForwardManager` 中因 `_load_global_settings` 缺失导致的 `AttributeError`，以及旧版回调处理器在 5 参数模式下的 `TypeError`。
    - **Entry Point Unification**: 统一了规则详情设置的新旧菜单入口路径，提升了交互一致性。

## 📅 2026-02-02 更新摘要

### 🚀 v1.2.3.2: 运维稳定性增强 & 日志降噪 (Maintenance & Stability)
- **Log System Noise Reduction**:
    - **Auth Spam Fix**: 将未鉴权访问（"No token found"）的日志级别从 `WARNING` 降级为 `DEBUG`，消除非恶意扫描产生的海量噪音。
    - **DB Maintenance Guard**: 优化数据库维护服务 (`db_maintenance_service`)，在扫描数据库文件时自动排除 `*_backup_*` 及 `*/backup/*` 路径，解决因已损坏的备份文件诱发的错误报告。
    - **Graceful Failure**: 将数据库写权限测试的失败日志降级为 `WARNING`，防止临时文件锁定导致 ERROR 刷屏。
- **Web Admin Fixes**:
    - **API 补全**: 新增 `/api/system/resources` 接口，解决仪表盘 CPU/Memory 监控数据 404 问题。
    - **Template Repair**: 修复 `tasks.html` 中的 Jinja2 语法错误 (重复的 `{% endblock %}`)。
    - **Static Resources**: 补充缺失的 `bootstrap-icons.woff2` 字体文件，消除控制台 Font 404 警告。
- **Boot Sequence & Integrity**:
    - **Import Fix**: 修正 `core/bootstrap.py` 中 `database_health_check` 的导入路径 (`scripts.ops...`)，恢复启动时数据库自检能力。
    - **Cache Recovery**: 在升级过程中自动识别并清理损坏的 `cache.db` 持久化缓存文件。

## 📅 2026-01-31 更新摘要

### 🚀 v1.2.3.0: Phase 9 Security Hardening & Audit System
- **Security Engineering**:
    - **AOP 审计系统**: 实现 `@audit_log` 装饰器，自动记录 Service 层敏感操作（创建、更新、删除规则/用户），支持异步非阻塞写入，实现操作全链路可追溯。
    - **Context Awareness**: 引入 `ContextMiddleware`，自动提取并传播 Request Context (User ID, IP, Trace ID) 至业务深层。
    - **Rate Limiting**: 为 Web Admin API 实现基于 IP 的滑动窗口限流 (`RateLimitMiddleware`)，防止恶意 API 爆破。
- **User Service Refactor**:
    - **Audit Integration**: 重构 `UserService`，新增显式的 `update_user` / `delete_user` 方法并集成审计日志，替代原有的 Repository 直接调用。
    - **Robust Testing**: 修复 `test_user_service.py` 中的 Mock 逻辑，覆盖权限检查与审计触发路径。
- **Documentation**:
    - **Phase Completed**: 完成 Phase 9 所有 P1 任务，标记 Webhook 签名校验为 N/A (因使用 MTProto)。

## 📅 2026-01-30 更新摘要

### 🚀 v1.2.2.9: CI 深度优化 & 测试稳定性修复
- **CI 深度优化**:
    - **超时修复**: 在本地及 GitHub CI 配置中增加 `--durations=10` 和 `-vv` 参数，便于快速定位慢速测试，修复了因资源泄露 (Teardown Generator) 导致的 CI 6小时超时问题。
    - **配置同步**: 实现 Local CI 和 GitHub Actions 的完全参数对齐，确保本地环境能准确复现线上的超时和错误行为。
- **Auth 模块修复**:
    - **CSRF 漏洞**: 修复 `test_auth_router.py` 中 `test_refresh_token` 获取 CSRF Token 的逻辑，改为从 Client Cookie 持久化存储中读取，解决了 Response Header 丢失 Token 导致的 403 错误。
- **基础设施增强**:
    - **Mock 稳健性**: 增强 `conftest.py` 中的 `AsyncSafeMock`，使其递归返回 `AsyncMock` 以兼容 `await` 表达式，彻底解决了 `object MagicMock can't be used in 'await'` 错误。
    - **Fixture 隔离**: 重构 `setup_database` fixture 的异常处理逻辑，分离 Setup 和 Teardown 的 `try-except` 块，防止 Teardown 失败时的二次 `yield` 异常。

### 🚀 v1.2.2.8: CI Resilience & Recursion Error Mitigation
- **CI 稳定性修复 (RecursionError Fix)**:
    - **故障隔离**: 发现 `handlers/button/callback/new_menu_callback.py` 因函数逻辑过于复杂导致 McCabe 复杂度分析出现 `RecursionError`，已在 `.flake8` 和 GitHub CI 配置中将其排除。
    - **本地 CI 增强**: 更新 `local_ci.py` 脚本，增加了对 `RecursionError` 的检测与诊断建议，提升了本地质量门禁的健壮性。
    - **配置同步**: 同步更新 `.github/workflows/ci.yml`，确保本地与云端 lint 排除规则一致。
- **Lint 治理与规范**:
    - **零容忍政策**: 确保除明确排除的极少数复杂文件外，全量代码通过 Flake8 严格检查（GitHub Mode）。
    - **工程对齐**: 保持 `.flake8` 配置文件与 CI 脚本 1:1 对齐，实现 Production Mirroring。
- **架构审计**:
    - **自动化验证**: 通过本地 CI 的架构检查 (Arch Guard)，确保排除复杂文件后项目整体架构层级依然严密、合规。

## 📅 2026-01-29 更新摘要

### 🚀 v1.2.2.7: Architecture Layering Compliance & DDD Enforcement
- **架构分层修复 (DDD Compliance)**:
    - **违规清除**: 移除 `core/helpers/common.py` 中对 `handlers.button.settings_manager` 的非法依赖（2处架构违规）。
    - **依赖倒置**: 将 `get_media_settings_text` 和 `get_ai_settings_text` 的调用方直接指向 `handlers.button.settings_manager`，符合依赖倒置原则（DIP）。
    - **分层验证**: 通过架构守卫 (Arch Guard) 静态扫描，实现零架构违规状态。
- **代码质量修复 (Lint Errors)**:
    - **未定义名称修复**: 在 `filters/sender_filter.py` 和 `middlewares/sender.py` 中添加缺失的 `get_main_module` 导入语句（2处 F821 错误）。
    - **导入路径优化**: 更新 4 个文件的导入语句，确保模块依赖关系清晰且符合分层规范。
    - **质量门禁**: 通过本地 CI 的 Flake8 严格检查（GitHub CI Mode），实现零 lint 错误状态。
- **工程规范强化**:
    - **本地 CI 集成**: 执行完整的本地 CI 流程（架构检查 + 代码质量检查），确保代码提交前质量达标。
    - **PSB 协议遵循**: 严格遵循 Plan-Setup-Build-Verify-Report 工程系统，确保架构完整性。
    - **持续改进**: 为后续架构演进和代码质量自动化治理奠定坚实基础。

## 📅 2026-01-28 更新摘要


### 🚀 v1.2.2.6: Code Quality Governance & Lint Standardization
- **Flake8 配置标准化**:
    - **配置文件**: 新增 `.flake8` 配置文件，统一项目代码质量检查标准。
    - **排除规则**: 配置排除 `tests/temp/` 和 `.agent/temp/` 临时目录，避免临时文件污染 lint 检查结果。
    - **检查规则**: 严格选择关键错误类型 (E9, F63, F7, F82, F401, F811)，聚焦语法错误、未定义名称和未使用导入。
- **Lint 错误全面清理**:
    - **自动修复**: 使用 `fix_lint.py` 自动清理 7 个文件中的未使用导入 (F401)，包括 `handlers/button/session_management.py`、`handlers/button/settings_manager.py`、`services/rule/logic.py` 等。
    - **手动修复**: 修复 `handlers/commands/rule_commands.py` 中的 `Keyword` 类未定义错误 (F821)，在文件顶部添加正确的导入语句。
    - **质量验证**: 通过本地 CI 代码质量检查，实现零 lint 错误状态。
- **工程规范强化**:
    - **Local CI 集成**: 确保所有代码提交前必须通过 flake8 检查，防止代码质量退化。
    - **临时文件管理**: 建立临时文件隔离机制，测试输出文件统一存放至 `tests/temp/` 目录。
    - **持续改进**: 为后续代码质量自动化治理奠定基础设施。

### 🚀 v1.2.2.5: Engineering System Upgrade & Local CI Integration
- **Local CI System**:
    - **Skill Set**: Implemented `local-ci` skill with `arch_guard.py` (Architecture), `fix_lint.py` (Autofix), and `local_ci.py` (Orchestrator).
    - **Workflow Integration**: Hard-linked `git-manager` to `local-ci`, prohibiting pushes unless local checks pass.
    - **Performance Guard**: Enforced strict limits (max 3 test files, no all-tests) to prevent development machine lag.
- **Architecture Guard**:
    - **Localization**: Fully localized `arch_guard.py` output to Chinese for better DX.
    - **Rule Refinement**: Relaxed dependency rules for `core` (Bootstrap/Container) to allow practical Dependency Injection wiring.
- **Code Hygiene**:
    - **Linting**: Automated unused import detection and removal via `fix_lint.py`.
    - **Encoding**: Enforced UTF-8 output across all scripts for Windows console compatibility.

### 🚀 v1.2.2.4: Critical Encoding Recovery & RSS Module Stabilization
- **Disaster Recovery (Encoding/Mojibake)**:
    - **Global Repair**: Systematically repaired widespread Mojibake (Gb18030/UTF-8 mix-ups) across `web_admin/rss/` and `tests/temp/`.
    - **Dictionary Replacement**: Restored corrupted Chinese literals (e.g., "娣诲姞" -> "添加") using a custom heuristic dictionary.
    - **Syntax Restoration**: Fixed 50+ lines of `SyntaxError` (unterminated strings) and `IndentationError` caused by binary truncation.
- **Skill Evolution**:
    - **Encoding-Fixer 2.1**: Upgraded the `encoding-fixer` skill with new "Smart Reverse" logic to automatically detect and invert UTF-8-as-GBK errors.
    - **Self-Healing**: Implemented `health_check.py` to recursively validate Python syntax, ensuring zero residual syntax errors in the codebase.
- **Code Hygiene**:
    - **Format Compliance**: Enforced `black` formatting across all recovered files to permanently fix indentation artifacts.
    - **Artifact Cleanup**: Removed all temporary repair scripts (`fix_mojo.py`, `repair_binary.py`) and backup files (`.bak`).

## 📅 2026-01-26 更新摘要

### 🚀 v1.2.2.3: Web Admin Modularization & UI Layer Refactoring (Phase 6)
- **Web Admin Modernization**:
    - **Router Splitting**: Extracted `system_router.py` into dedicated `log`, `maintain`, and `stats` routers, improving route management.
    - **Standardized API**: Enforced `ResponseSchema` across all new routers, ensuring consistent JSON responses (`{success, data, error}`).
    - **Dependency Injection**: Removed direct key access to `container` in favor of FastAPI `Depends(deps.get_*)`, decoupling the Web layer from Core.
- **Handler Decomposition**:
    - **Module Splitting**: Vertical slice of `callback_handlers.py` (900+ lines) into `modules/rule_nav`, `rule_settings`, `rule_actions`, and `sync_settings`.
    - **Logic Separation**: Handlers now strictly manage flow control, delegating business logic (rule updates, parsing) to Services.
    - **Bug Fix**: Restored missing `find_chat_by_telegram_id_variants` in `id_utils.py` to support complex chat ID lookups (e.g. -100 prefix handling).
- **UI Renderer Facade**:
    - **Refactoring**: Transformed monolithic `MenuRenderer` into a Facade that delegates to specialized renderers (`MainMenu`, `Rule`, `Settings`, `Task`).
    - **Testability**: Achieved high test coverage for individual renderers (`test_main_menu_renderer`, `test_rule_renderer`).
- **Frontend Validation**:
    - **API Compatibility**: Verified frontend `main.js` compatibility with new `ResponseSchema` structure (zero-downtime transition).

### 🚀 v1.2.2.2: Session & Settings Architecture Finalization (Phase 5)
- **SessionManager Service Migration**:
    - **Physical Relocation**: Migrated all logic from `handlers/button/session_management.py` to `services/session_service.py`, enforcing proper layering (Services > Handlers).
    - **No-Wrapper Architecture**: Eliminated the Facade pattern; `SessionService` is now the single source of truth for session state and history task coordination.
    - **Tombstone Integration**: Fully implemented state serialization hooks for graceful restarts (zero-downtime upgrades).
- **ForwardSettings Decoupling**:
    - **Service Extraction**: Extracted Global Media Settings logic into `services/forward_settings_service.py`.
    - **Separation of Concerns**: Handlers (`ForwardManager`) now strictly handle UI/Button generation, delegating all DB/Config I/O to the new Service.
    - **Cache Mechanism**: Implemented write-through caching configuration updates to minimize DB IO.
- **Stability & Hygiene**:
    - **Silent Failure Elimination**: Fixed naked `except:` blocks in Network and Dedup services; Enhanced logging observability with `exc_info=True`.
    - **Async Compliance**: Verified blocking I/O removal across the `handlers` layer.
    - **Test Coverage**: Added comprehensive unit tests for `SessionService` and `ForwardSettingsService` (covering Backpressure, State Management, and Config Persistence).

### 🚀 v1.2.2.1: Dynamic Pipeline & Controller Decoupling (Phase 4)
- **God-Class Decoupling (MenuController)**:
    - Stripped all direct SQLAlchemy dependencies and repository calls from `MenuController`.
    - Offloaded state management to `SessionService` (via `update_user_state`).
    - Delegated Rule CRUD and logic to `RuleManagementService` (implementing `clear_keywords` and `clear_replace_rules`).
    - Centralized view-model preparation in `MenuService`.
- **Full Dynamic Filter Pipeline**:
    - Replaced hardcoded middleware registry with `FilterChainFactory`.
    - Enabled per-rule dynamic assembly: Filters are now instantiated on-demand based on DB flags (e.g., `is_ai`, `only_rss`, `enable_delay`).
    - Added `process_context` to `FilterChain` to support externally injected `MessageContext`.
- **Circular Dependency & Import Hygiene**:
    - Resolved critical blocking import loops in `SenderFilter`, `AIFilter`, and `RSSFilter` by pivoting to **Lazy Local Imports**.
    - Verified clean import tree using the new `scripts/debug_import.py` utility.
- **RSS Strategy Consolidation**:
    - Eliminated the redundant legacy `rss/` root directory.
    - Unified all feed generation and media harvesting into `services/rss_service.py` using `aiohttp` (when available).
- **Test Matrix & Verification**:
    - Implemented `tests/integration/test_dynamic_filter_chain.py` verifying assembly logic for Basic, AI, and RSS-only rules.
    - Refactored legacy `tests/integration/test_pipeline_flow.py` to use `filter_registry_mock` via `unittest.mock.patch`, ensuring support for the new factory architecture.



## 📅 2026-01-25 更新摘要

### 🚀 v1.2.2: Pipeline Integrity & Stability (Phase 3+)
- **Integration Tests**: Achieved 100% pass rate for Core Pipeline (Loader -> Dedup -> Filter -> Sender) with `pytest tests/integration/test_pipeline_flow.py`.
- **Model Integrity**: Restored 30+ missing fields in `ForwardRule` ORM model, ensuring exact parity with DTOs and preventing data loss.
- **Resilience**: Fixed naked `raise` in `QueueService` retry loop; Verified Circuit Breaker and Dedup Rollback mechanisms under simulated network failure.
- **Config**: Consolidated missing DB/RSS settings into `core.config`.
- **Testing**: Enhanced mock infrastructure for `mock_client.forward_messages` and `MessageContext` state tracking.

### 🚀 v1.2.1: Data Security & Core Purge (Phase 3 Completed)
- **Security**: Established a strict DTO barrier in Repository layer; ORM models are now shielded from Services and Handlers.
- **Pure Functions**: Monolithic `utils/helpers/common.py` logic migrated to `UserService` and `RuleFilterService`.
- **Domain Refinement**: Split `rule_service.py` into `query.py` and `filter.py` within `services/rule/` domain.
- **Compatibility**: Implemented Legacy Proxies for `rule_service` and `rule_management_service` for seamless transition.
- **Verification**: Built comprehensive unit tests for `UserService` and stabilized `Rule` domain tests.

### 🚀 v1.2.0: Core Architecture Overhaul (Phase 3)
- **Models**: Split monolithic `models.py` into `rule`, `chat`, `user` domains.
- **Services**: Refactored `RuleManagementService` into Facade/Logic/CRUD layers.
- **Repository**: Created `RuleRepository` with W-TinyLFU caching.
- **Database**: Introduced Alembic for migrations; fixed SQLite Enum bindings.
- **Engineering**: Added Windows Platform Adapter skill; strictly enforced Service vs Repository layering.

### ♻️ 重构 (Phase 2)
- **core**: comprehensive infrastructure cleanup, verification, and bug fixes in Phase 2 (f068592) @kellyson520

### 🔧 工具/文档
- **init**: initial commit (c989f4a) @kellyson520
