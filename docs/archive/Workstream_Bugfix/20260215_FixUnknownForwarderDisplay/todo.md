# 修复转发记录显示 unknown 为频道名

## 背景 (Context)
用户反馈在执行记录（History）页面中，转发记录的“来源实体”和“目标实体”显示为 "Unknown"，希望显示为真实的频道名称。

## 待办清单 (Checklist)

### Phase 1: 问题分析与验证
- [x] 确定前端页面：`web_admin/frontend/src/pages/History.tsx`
- [x] 确定后端接口：`/api/rules/logs` -> `rule_viz_router.py`
- [x] 确定数据映射：`RuleDTOMapper.log_to_dict`
- [x] 确定仓库实现：`StatsRepository.get_rule_logs`

### Phase 2: 后端逻辑修复
- [x] 修改 `StatsRepository.get_rule_logs` 使用 `joinedload` 预加载 `rule`, `rule.source_chat` 和 `rule.target_chat`
- [x] 修改 `StatsRepository.get_recent_activity` 同样预加载相关实体
- [x] (可选) 检查 `RuleDTOMapper.log_to_dict` 的异常处理是否掩盖了关键错误

### Phase 3: 验证与验收
- [x] 启动后端服务并检查 API 返回数据
- [x] 在前端页面确认“来源实体”和“目标实体”已正确显示
- [x] 归档任务报告

## 技术策略 (Strategy)
使用 SQLAlchemy 的 `joinedload` 机制解决 N+1 问题并确保在转换为 DTO 时相关关联对象已加载，从而避免触发延迟加载（在异步环境下可能失败）或因为未加载而返回 "Unknown"。
