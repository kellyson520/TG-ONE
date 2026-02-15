# 修复 Web 端 Bug (2026-02-15)

## 背景 (Context)
修复用户报告的 Web 管理界面/后端中的 4 个具体 Bug：
1. 统计信息中出现"Unknown"消息类型分布。
2. 操作日志详情显示为"Unknown"。
3. 获取任务队列失败。
4. 打开日志面板导致白屏（前端崩溃或死循环）。

## 策略 (Strategy)
- 分析 `stats_router.py` 和 `analytics_service.py` 以解决"Unknown"消息类型问题。
- 分析 `services` 或 `routers` 以解决"Unknown"操作详情问题。
- 分析 `services/worker_service.py` 或相关文件以解决任务队列问题。
- 分析前端（如果可行）或后端日志 API 以解决"白屏"问题。如果是后端发送了坏数据，则修复后端。如果是前端问题，尝试修复前端代码。

## 任务清单 (Checklist)

### Phase 1: 修复消息类型分布未知问题 (Unknown Message Type)
- [x] **审计数据源**: 检查 `RuleLog` 数据库表中 `message_type` 字段的现有数据，确认是否存在 NULL 或空字符串。
- [x] **定位聚合逻辑**: 分析 `services/analytics_service.py` 中的 `get_detailed_stats` 方法，查看类型分布是如何计算的。
- [x] **修复写入逻辑**: 检查 `ForwardService` 或日志记录器，确保在记录日志时正确设置 `message_type` (如 'text', 'photo', 'video')。`SenderMiddleware` 已实现，`forward_log_writer` 已补充。
- [x] **数据清洗/映射**: 在 `analytics_service.py` 中添加映射逻辑，将 `None` 或未知类型统一映射为 "Text" 或 "Other"，避免前端显示 "Unknown" 或崩溃。
- [x] **增加单元测试**: 编写测试用例，模拟包含 NULL `message_type` 的日志数据，验证 `get_detailed_stats` 返回的分布数据是否正常。
- [x] **UI 验证**: 刷新 Dashboard，确认饼图/统计条不再显示 "Unknown"。

### Phase 2: 修复操作详情未知问题 (Unknown Operation Details)
- [x] **定位 API**: 确认是 `/api/system/stats` (recent_activity) 还是 `/api/logs` 接口返回了 "Unknown" 详情。
- [x] **代码追踪**: 检查 `analytics_service.py` 中的 `search_records` 方法及其对 `RuleLog` 数据的处理。
- [x] **字段映射修复**: 发现 `RuleLog` 模型中可能缺失 `details` 字段，或者该字段未被正确填充。检查是否需要从 `action` 或 `message_text` 构造详情。
- [x] **完善日志记录**: 修改核心业务逻辑（如 `ForwardService`），在创建 `RuleLog` 时写入结构化的 `extra_info` 或详细描述。`forward_log_writer.py` 已修复。
- [x] **前端适配**: 如果后端无法回溯历史详情，确保前端在详情为空时显示默认友好的文本（如 "无详细信息"）而不是 "Unknown"。
- [x] **验证修复**: 触发一条新的转发规则，检查生成的日志详情是否包含预期内容（如 "转发至 Channel A"）。

### Phase 3: 修复获取任务队列失败问题 (Task Queue Failure)
- [x] **复现问题**: 调用 `/api/system/tasks` 接口，查看服务端抛出的具体异常堆栈（500 Error）。
- [x] **检查模型属性**: 再次确认 `web_admin/routers/system/stats_router.py` 中 `TaskQueue` 的字段访问（如 `retry_count` vs `attempts`, `error_log` vs `error_message`）是否已完全修复。
- [x] **处理序列化错误**: 检查 `task_data` 字段（JSON）是否存在解析错误的风险，添加 `try-catch` 块防止单个坏任务导致整个列表接口崩溃。
- [x] **空值处理**: 确保 `TaskQueue` 中的可选字段（如 `scheduled_at`, `updated_at`）在为 `None` 时能被 Pydantic schema 正确处理。
- [x] **分页逻辑检查**: 验证 `page` 和 `limit` 参数的边界处理，防止数据库查询越界错误。
- [x] **验证修复**: 确保 `/api/system/tasks` 返回 HTTP 200 及正确的 JSON 列表结构。

### Phase 4: 修复日志面板白屏问题 (Log Panel White Screen)
- [x] **定位崩溃源**: 确认白屏是因为接口超时（数据量过大）、HTTP 500 错误，还是前端 JS 处理特定数据时崩溃。
- [x] **限制返回长度**: 在 `logs_router.py` 或 `analytics_service.py` 中，强制限制单条日志 `message_text` 或详情的返回长度（如截断为 500 字符），防止超大文本撑爆前端内存。
- [x] **特殊字符过滤**: 检查日志中是否存在未转义的 HTML 标签或特殊控制字符，导致前端渲染器解析失败。
- [x] **分页性能优化**: 如果日志表过大，优化 `search_records` 的 SQL 查询性能（增加索引或优化 `LIKE` 查询），防止接口超时。
- [x] **增强异常处理**: 在日志序列化过程中捕获所有字段级异常，确保即使某条日志损坏，接口也能返回其他正常日志。
- [x] **前端防护 (可选)**: 如果能修改前端，增加 `Error Boundary` 或 `try-catch` 块包裹日志渲染组件。

### Phase 5: 修复规则列表获取失败 (Fix Rule List Fetch Failure)
- [x] **修复 DTO 定义缺失**: 在 `schemas/rule.py` 中为 `KeywordDTO` 和 `ReplaceRuleDTO` 添加 `id` 字段，解决 `RuleDTOMapper` 访问 `id` 属性并在 DTO 转换中丢失的问题。
- [x] **修复 ChatDTO 定义缺失**: 在 `schemas/chat.py` 中为 `ChatBase` 添加 `title` 字段，解决 `RuleDTOMapper` 访问 `source_chat.title` 时的 `AttributeError`。
- [x] **验证修复**: 通过测试脚本确认 DTO 属性访问正常，API 应能正确返回规则列表。
