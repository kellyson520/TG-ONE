# 任务: 修复转发模式枚举失效、媒体组 N+1 隐患、路由解包风险及去重逻辑冗余

## 背景 (Context)
在深度审查后发现以下问题：
1. `RuleFilterService` 中 `Enum` 对象与字符串比较导致匹配失效。
2. `InitFilter` 在处理媒体组时，每个子消息都发起 API 调用，存在严重的 N+1 问题。
3. `handle_callback` 在路由匹配失败时尝试解包 `None` 导致崩溃。
4. `InitFilter` 包含老旧且冗余的去重签名计算逻辑。

## 待办清单 (Checklist)

### Phase 1: Build - 核心修复 (Fixed)
- [x] **修复枚举比较**: 将 `forward_mode` 统一为字符串或直接比较枚举成员。(Done)
- [x] **优化媒体组处理**: 引入缓存机制防止媒体组 N+1 API 调用。(Done)
- [x] **加固路由分发**: 增加对 `callback_router.match()` 返回值的空值判定。(Done)
- [x] **清理冗余去重**: 移除 `InitFilter` 中与 `smart_deduplicator` 重叠的老旧代码。(Done)

### Phase 2: Verify & Report
- [x] 验证受影响模块的逻辑正确性。(Done)
- [x] 确认在高负载/媒体组场景下的性能表现。(Done)
- [x] 提交任务报告 `report.md`并闭环。(Done)

## 结论 (Conclusion)
所有发现的逻辑错误与性能风险已解决。
