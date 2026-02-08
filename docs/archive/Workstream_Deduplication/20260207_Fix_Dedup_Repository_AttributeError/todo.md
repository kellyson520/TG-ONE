# Fix DedupRepository AttributeError

## Context
去重引擎 `SmartDeduplicator` 在后台刷写缓冲区时调用了 `repo.batch_add_media_signatures`，但 `DedupRepository` 中对应的函数名为 `batch_add`，导致 `AttributeError`。

## Checklist

### Phase 1: 问题修复
- [x] 在 `repositories/dedup_repo.py` 中将 `batch_add` 重命名为 `batch_add_media_signatures` 并添加别名。
- [x] 在 `repositories/dedup_repo.py` 中增加字段过滤，增强 `bulk_insert_mappings` 的健壮性。
- [x] 完善 `SmartDeduplicator._flush_buffer` 的异常处理与数据回滚（重入队）机制。
- [x] 修复 `SimilarityStrategy` 的 `NameError` (未定义变量 `comparisons`)。
- [x] 修复 `KeywordFilter` 与 `DedupMiddleware` 双重校验导致的“全部误判为重复”逻辑冲突。
- [x] 在 `DedupMiddleware` 中增加历史任务跳过去重逻辑。
- [x] 编写并验证 `DedupRepository` 批量写入的单元测试。
- [x] 更新文档与进度。
