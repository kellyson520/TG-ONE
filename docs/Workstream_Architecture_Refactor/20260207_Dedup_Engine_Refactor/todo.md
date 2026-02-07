# 任务清单：智能去重引擎重构 (SmartDeduplicator Refactor) - 轻量化

## 阶段 1: 指纹逻辑剥离 (Tools Extraction)
- [x] 创建 `services/dedup/tools.py`。
- [x] 将 **无状态及纯函数** (`_generate_*`系列, `_calculate_simhash`, `_extract_media_features`) 方法从 `engine.py` 移动到 `tools.py`。
- [x] 修改 `engine.py` 调用这些新函数。确保现有单元测试全部通过。
`tools.py` 包含但不限于:
  - `_generate_signature`
  - `_generate_content_hash` -> `generate_content_hash`
  - `_calculate_simhash` -> `calculate_simhash`
  - `_is_video` -> `is_video`
  - `_extract_video_file_id` -> `extract_video_file_id`
  - `_extract_stream_vector` -> `extract_stream_vector`

## 阶段 2: 策略接口定义 (Strategy Interface)
- [x] 创建 `services/dedup/types.py` (DedupResult, DedupContext, DedupConfig)。
- [x] 创建 `services/dedup/strategies/base.py` (BaseDedupStrategy 抽象类)。

## 阶段 3: 策略拆分实现 (Strategy Refactor)
- [x] **签名策略**: 创建 `services/dedup/strategies/signature.py`。迁移 `_check_signature_duplicate` 中的时间窗口/PCache/DB查询逻辑。
- [x] **视频策略**: 创建 `services/dedup/strategies/video.py`。迁移 `_check_video_duplicate_by_file_id` 和 `_check_video_duplicate_by_hash`。
- [x] **内容策略**: 创建 `services/dedup/strategies/content.py`。迁移 `_check_content_hash_duplicate`。
- [x] **相似度策略**: 创建 `services/dedup/strategies/similarity.py`。迁移 `_check_similarity_duplicate`。

## 阶段 4: Facade 瘦身与编排 (Engine Simplification)
- [x] 重构 `services/dedup/engine.py` 的 `check_duplicate`。
- [x] 在 `__init__` 中初始化策略列表。
- [x] 将原有上下文（缓存、Repo引用）封装到 `DedupContext`。
- [x] 循环执行策略 `process(ctx)`，替代原有的长 if-dlse 链。

## 阶段 5: 清理与验证 (Verify & Cleanup)
- [ ] 确保测试覆盖率无下降 (`tests/unit/services/test_smart_deduplicator.py`)。
- [ ] 代码清理：移除 `engine.py` 中所有的旧私有方法（如下划线开头的检查函数），除非其被新策略公用。
