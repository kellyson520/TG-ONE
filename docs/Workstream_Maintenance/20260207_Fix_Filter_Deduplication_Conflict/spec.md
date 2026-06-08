# 技术方案：过滤器与去重协同优化

## 问题分析
1. **GlobalFilter 逻辑缺口**：`GlobalFilter` 在判定媒体屏蔽且无文本时，虽然设置了 `context.should_forward = False`，但函数末尾统一返回了 `True`，导致处理链错误地继续执行到 `KeywordFilter`。
2. **去重维度冲突**：`SmartDeduplicator` 基于 `event.message` 生成签名。即使 `GlobalFilter` 标记了 `media_blocked`，去重引擎仍然会计算图片/视频的 `signature`。若 24 小时内有相同媒体，则命中去重，导致"仅转发文本"的任务失败。

## 解决方案

### 1. GlobalFilter 闭环
修改 `filters/global_filter.py`:
确保在结尾处返回 `context.should_forward` 而非硬编码的 `True`。

### 2. KeywordFilter 语义感知
修改 `filters/keyword_filter.py` 中的 `_check_smart_duplicate`:
- 增加对 `context.media_blocked` 的判断。
- 调用 `smart_deduplicator.check_duplicate` 时增加 `skip_media_sig` 参数。

### 3. SmartDeduplicator 接口扩展
修改 `services/dedup/engine.py` 的 `check_duplicate`:
- 增加参数 `skip_media_sig: bool = False`。
- 当 `skip_media_sig` 为 `True` 时，直接略过签名的生成与比对逻辑。

## 预期效果
- 当全局屏蔽图片时，发送图片+文本，第一条和第二条（不同图片的相同文本或相同图片的不同文本）都能根据文本去重逻辑（若开启）独立判断，而不会因为图片相同而误杀文本。
