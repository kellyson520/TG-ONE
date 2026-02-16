# 任务报告: 修复 Web 页面记录详情未知与任务列表获取失败

## 摘要 (Summary)
成功修复了 Web 管理界面中的两个关键问题：
1. **记录详情未知**: 修复了“转发记录”搜索结果中来源/目标频道显示为 "Unknown" 或 ID 的问题。
2. **任务列表失败**: 修复了“任务队列”页面加载失败的问题（由于 SQLite 日期存储格式不一致导致的后端崩溃）。

## 架构变更 (Architecture Refactor)
- **Analytics Service**: 
    - `search_records` 方法引入了完整的 `joinedload` 策略，预加载 `Rule -> SourceChat` 和 `Rule -> TargetChat` 关联。
    - 统一了解析逻辑，确保返回给前端的是易读的频道名称而非原始 ID。
- **Stats Router**:
    - `get_tasks_list` 端点增加了对日期字段的鲁棒性处理。使用 `hasattr(..., 'isoformat')` 进行守护，能够兼容处理 `datetime` 对象和 `string` 形式的日期，消除了 `AttributeError` 风险。

## 验证结果 (Verification)
- **单元测试**:
    - `tests/unit/services/test_analytics_service.py`: 4 项测试全部通过，验证了搜索结果的字段补全逻辑。
    - `tests/unit/web/test_task_list_bug.py`: 专门创建的回归测试通过，验证了在混合日期格式下任务列表的正确返回。
- **鲁棒性**: 经检查，系统现在能正确处理规则被删除或聊天信息缺失的极端情况，提供优雅的 "未知" 或 ID 回退。

## 后续建议 (Recommendations)
- 建议定期运行 `db-migration-enforcer` 技能以检查数据库中是否存在字段类型不一致的历史遗留数据。
- 建议各模块在序列化日期字段时，统一采用本文实现的守护模式。
