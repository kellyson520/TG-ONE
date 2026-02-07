# 任务交付报告: 修复智能去重过激拦截

## 1. 摘要 (Summary)
修复了智能去重系统过度拦截正常消息的问题。通过优化过滤器执行顺序与收紧媒体指纹生成算法，消除了因元数据相似或非目标消息触发去重而导致的误判。

## 2. 核心变更 (Architecture Refactor)
1. **Filtering Pipeline Upgrade**: `KeywordFilter` 逻辑调整，将去重 (`_check_smart_duplicate`) 移至关键词匹配成功 *之后*。
   - **Before**: 收到消息 -> Check Dedup (Blocked!) -> Check Keyword.
   - **After**: 收到消息 -> Check Keyword (Pass) -> Check Dedup -> Forward.
   - **Benefit**: 降低去重计算开销，避免非相关消息污染去重缓存，彻底解决非目标消息被去重误伤的问题。

2. **Fingerprinting Algorithm Enhancement**: `tools.py` 移除弱特征签名。
   - 移除: 仅凭 `duration` 生成的 `video_nodata:{duration}` 签名。
   - 移除: 仅凭 `size` 生成的 Photo 签名。
   - 移除: 仅凭 `size` 生成的 Document 签名。
   - **Result**: 必须拥有 Unique ID (FileID/PhotoID) 或强内容哈希才能触发去重，防止元数据碰撞。

3. **Batched Write Verification**: 修正单元测试以适应 `SmartDeduplicator` 的异步批量写入机制，确保测试准确反映系统行为。

## 3. 验证结果 (Verification)
- [x] `tests/unit/services/test_dedup_service.py`: 通行 (6 passed, 1 skipped)
- [x] `tests/unit/services/test_smart_deduplicator.py`: 通行 (5 passed)

## 4. 后续建议
- 监控 `Dedup` 相关 Prometheus 指标，观察去重命中率是否回归正常水平。
- 建议定期清理 `time_window_cache` 以释放长期不再活跃的群组内存。
