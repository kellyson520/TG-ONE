# 技术方案: 空文本消息去重策略降级 (Spec)

## 背景
智能去重引擎 (SmartDeduplicator) 在处理消息时，会根据配置计算文本哈希和签名。
当 `message_text` 为空或仅包含空白字符时，不同消息生成的哈希值相同，导致全局范围内的无文本消息出现哈希碰撞。

## 修复路径

### 1. Filter 层拦截与修饰
在 `KeywordFilter._check_smart_duplicate` 中，在构造 `rule_config` 后，增加对 `context.message_text` 的校验。

**伪逻辑**:
```python
current_text = getattr(context, 'message_text', None)
if not current_text or not str(current_text).strip():
    rule_config['enable_content_hash'] = False
    rule_config['enable_smart_similarity'] = False
    logger.debug("消息无文本，已禁用文本去重策略以防止误判")
```

### 2. 依赖检查
`xxhash` 是 `SmartDeduplicator` 用于计算签名的高效库。若缺失会导致功能异常。
需通过 `pip list` 或直接运行测试代码验证其可用性。

## 影响范围
- `filters/keyword_filter.py`
- 系统转发逻辑：增加了无文本消息的通过率（正确性修复）。
- 性能：无负面影响，减少了空哈希计算和不必要的相似度比对。
