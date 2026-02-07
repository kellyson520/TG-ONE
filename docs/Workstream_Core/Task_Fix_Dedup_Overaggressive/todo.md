# 修复智能去重误判与过激拦截 (Fix Aggressive Deduplication)

## 背景 (Context)
用户反馈智能去重系统误判严重，拦截了大量正常任务 ("智能去重命中... 时间窗口内重复")。
经分析，原因主要为：
1. `KeywordFilter` 中去重逻辑先于关键词匹配执行，导致即使是不相关的消息也被纳入去重计算，可能导致误判或不必要的资源消耗。
2. 指纹生成算法 (`tools.py`) 对某些媒体类型的 Fallback 过于激进（如仅凭 duration 生成签名），导致不同内容的媒体文件因元数据相似而被误判为重复。

## 策略 (Strategy)
1. **调整过滤顺序**: 将去重检查移至关键词/发送者匹配 *之后*。只有匹配关键词且符合发送者规则的消息，才进行去重检查。
2. **收紧签名算法**: 移除 `generate_signature` 中的弱特征 Fallback（如 `video:{duration}`），在能够获取 Unique ID 时严格依赖 ID，否则返回 None (交由 Content Hash 处理)。

## 待办清单 (Checklist)

### Phase 1: 核心逻辑修正 (Core Logic)
- [x] 重构 `filters/keyword_filter.py`: 移动 `_check_smart_duplicate` 到 `sender_ok` 和 `keyword_ok` 均通过之后执行。
- [x] 优化 `services/dedup/tools.py`: 移除 Photo/Video/Document 的纯属性（如大小/时长）兜底签名，强制要求 ID。

### Phase 2: 验证 (Verification)
- [x] 运行 `pytest tests/unit/services/test_dedup_service.py` 确保服务层逻辑正常。
- [ ] 运行 `pytest tests/unit/services/test_smart_deduplicator.py` 确保去重引擎逻辑正常。

### Phase 3: 交付 (Delivery)
- [ ] 生成 `report.md`。
