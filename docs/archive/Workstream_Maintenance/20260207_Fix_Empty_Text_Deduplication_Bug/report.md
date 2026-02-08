# 任务报告: 修复空文本消息智能去重误判 (Report)

## 任务背景 (Summary)
用户反馈在启动转发器后，所有消息都被智能去重系统命中导致无法转发。经分析发现，当消息不含文本（如纯视频、纯图片）时，去重引擎计算的空文本哈希值会发生全局冲突。此外，环境依赖 `xxhash` 的缺失也可能影响指纹计算的稳定性。

## 解决详情 (Implementation)

### 1. 过滤器逻辑加固
在 `filters/keyword_filter.py` 的 `_check_smart_duplicate` 方法中增加了前置校验：
- **空文本检测**: 检查 `context.message_text`。
- **策略降级**: 若文本为空或仅包含空白字符，强制将 `enable_content_hash` 和 `enable_smart_similarity` 设置为 `False`。
- **日志提示**: 降级时输出 DEBUG 日志，便于排查。

### 2. 依赖环境确认
- 验证 `xxhash` (v3.5.0+) 已在 `requirements.txt` 中。
- 经测试环境验证，`xxhash` 已正确安装 (v3.6.0)。

## 验证结论 (Verification)

### 单元测试
执行了 `tests/unit/filters/test_keyword_filter.py`，所有 21 项测试全部通过。
- **新增用例**: `test_keyword_filter_smart_dedup_empty_text`。
- **验证结果**: 确认在 `message_text` 为空时，去重引擎接收到的配置已成功禁用了文本维度策略。

### 日志输出示例
```text
2026-02-07 19:58:28 [  DEBUG] 消息无文本，已禁用文本去重策略以防止误判: RuleID=1
```

## 交付清单 (Manual)
- 已修复代码：`filters/keyword_filter.py`
- 已更新测试：`tests/unit/filters/test_keyword_filter.py`
- 已对齐文档：`docs/process.md`, `todo.md`
