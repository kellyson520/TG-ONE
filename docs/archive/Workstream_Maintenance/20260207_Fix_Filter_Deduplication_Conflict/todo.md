# 修复过滤器与去重引擎的冲突 (Fix Filter-Dedup Conflict)

## 背景 (Context)
当全局过滤器 (GlobalFilter) 设置为"屏蔽媒体但允许文本"时，消息虽然通过了 GlobalFilter，但在后续的 KeywordFilter 中会被智能去重引擎 (SmartDeduplicator) 拦截。
这是因为去重引擎使用了原始消息的媒体签名进行判重，而没有意识到该媒体实际上已被全局屏蔽。

## 策略 (Strategy)
1. 修正 `GlobalFilter` 的返回逻辑，确保当 `should_forward` 为 `False` 时中断处理链。
2. 增强 `KeywordFilter` 与 `SmartDeduplicator` 的协同，当上下文标记为 `media_blocked` 时，跳过媒体维度的签名判重。
3. 确保 `GlobalFilter` 设置 `media_blocked` 标志供后续过滤器使用。

## 待办清单 (Checklist)

### Phase 1: 逻辑修正
- [x] 修正 `filters/global_filter.py`：当 `should_forward` 为 `False` 时，`_process` 返回 `False`。
- [x] 增强 `filters/keyword_filter.py`：在执行 `_check_smart_duplicate` 前检查 `context.media_blocked`。
- [x] 优化 `services/dedup/engine.py`：支持在检查时忽略媒体签名。

### Phase 2: 验证与测试
- [x] 编写测试用例：模拟全局屏蔽图片，发送相同图片+不同文本，验证文本是否能正常转发。
- [x] 验证日志输出，确认过滤器中断行为符合预期。

### Phase 3: 交付
- [x] 生成 `report.md`
- [x] 更新 `process.md`
