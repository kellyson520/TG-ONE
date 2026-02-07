# Deduplication Engine & Repository Fix Report (2026-02-07)

## 问题描述
1. **AttributeError**: `SmartDeduplicator` 在刷写缓冲区时调用了不存在的方法 `batch_add_media_signatures`（实际库中名为 `batch_add`）。
2. **逻辑误判**: 全量消息被误判为“时间窗口内重复 (24小时)”。
3. **健壮性隐患**: 
   - `bulk_insert_mappings` 遇到模型多余字段会报错。
   - 刷写失败导致任务丢失。
   - `SimilarityStrategy` 中存在未定义变量 `comparisons` 引起的 `NameError`。

## 修复措施

### 1. Repository 层修复
- **接口对齐**: 将 `DedupRepository.batch_add` 重命名为 `batch_add_media_signatures` 并保留 `batch_add` 别名。
- **动态过滤**: 增加字段过滤逻辑，仅保留 `MediaSignature` 模型定义的列，增强了对 `SmartDeduplicator` 传递的冗余字段的兼容性。

### 2. Engine 引擎逻辑优化
- **双重校验冲突解决**: 发现 `DedupMiddleware` 已执行去重检查并“锁定”记录，而后续的 `KeywordFilter` 再次执行检查导致自碰撞。已移除 `KeywordFilter` 中的冗余去重逻辑。
- **历史记录跳过**: 在 `DedupMiddleware` 中增加 `is_history` 标记检测，确保历史补全任务不被去重拦截。
- **刷写可靠性**: 在 `_flush_buffer` 中增加 `try-except` 与异常回滚机制。写入数据库失败时，批处理数据将回滚至缓冲区头部（Reset to front），防止数据丢失。
- **代码修正**: 修复了 `SimilarityStrategy` 中 `comparisons` 变量未初始化的 Bug。

### 3. 自动化测试
- 编写了 `tests/unit/repositories/test_dedup_repo_batch.py`，验证了带有多余字段的批量写入逻辑。
- 验证了 `test_dedup_service.py` 中的端到端去重逻辑仍然有效。

## 验证结果
- **Unit Tests**: 2 Passed (Batch filtering verify).
- **Manual Log Check**: 确认 `Pipeline-Dedup` 能够正确识别重复消息且不再发生二次碰撞。

## 遗留问题
- 暂无。

---
**Report by Antigravity**
