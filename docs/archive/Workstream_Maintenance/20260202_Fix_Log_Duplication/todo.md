# 任务：修复日志重复与任务重复生成问题 (Fix Log & Task Duplication)

## 背景 (Context)
用户反馈日志中出现重复的处理记录，实际上是同一个消息被生成了两个不同的任务（Task ID 不同）。
经分析发现系统存在两个并行的消息监听器，且它们对 Chat ID 的标准化逻辑不一致，导致数据库 `unique_key` 去重失效。

## 策略 (Strategy)
1. **消除冗余监听器**：移除 `event_optimization.py` 中重复注册的 `NewMessage` 监听器，保留 `message_listener.py` 作为唯一入口。
2. **统一 ID 逻辑**：修正 `extract_chat_context.py` 中的 ID 处理逻辑，确保与全局 `normalize_chat_id` 保持一致，避免正负号或前缀差异。
3. **性能迁移**：将 `event_optimization.py` 中的预加载优化逻辑迁移至主监听器中（如批处理用户信息）。

## 待办清单 (Checklist)

### Phase 1: 故障排查与诊断
- [x] 分析日志，确认重复来源 (找到 `event_optimization.py` 和 `message_listener.py` 的并发冲突)
- [x] 验证 ID 差异 (发现 `-100...` 与 `100...` 的表现不一致)

### Phase 2: 逻辑修复
- [x] 移除 `core/helpers/event_optimization.py` 中的重复 `NewMessage` 监听器
- [x] 修正 `core/helpers/chat_context.py` 中的 ID 提取逻辑
- [x] 将用户信息预加载逻辑合并至 `listeners/message_listener.py`

### Phase 3: 验证与报告
- [x] 运行静态检查，确认无重复注册
- [x] 提交交付报告 `report.md`
- [x] 更新 `process.md`
