# 任务报告：修复过滤器与去重引擎逻辑冲突

## 摘要 (Summary)
成功解决了 GlobalFilter 在屏蔽媒体时，后续 KeywordFilter 仍因媒体签名冲突而跳过转发的问题。通过增强过滤器上下文语义和扩展去重引擎接口，实现了"屏蔽媒体但保留文本"时的准确去重。

## 变更详情 (Changes)

### 1. GlobalFilter 逻辑闭环
- **文件**: `filters/global_filter.py`
- **修改**: 确保在媒体被屏蔽且无文本可转发时，返回 `False` 以立即中断处理链。

### 2. 去重引擎语义化扩展
- **文件**: `services/dedup/engine.py`
- **功能**: `check_duplicate` 方法新增 `skip_media_sig` 参数。当开启时，将：
    - 跳过媒体元数据签名 (`signature`) 检查。
    - 跳过视频指纹 (`file_id`, `partial_hash`) 检查。
    - 在内容哈希 (`content_hash`) 计算中，如果存在媒体但要求跳过媒体签名，则强制降级为仅对文本进行哈希，确保文本去重逻辑依然有效。

### 3. KeywordFilter 协同增强
- **文件**: `filters/keyword_filter.py`
- **功能**: 检测到 `context.media_blocked` 时，自动向去重引擎传入 `skip_media_sig=True`。

## 验证结果 (Verification)
- **单元测试**: `tests/unit/filters/test_filter_dedup_link.py` (3/3 通过)
- **去重测试**: `tests/unit/services/test_smart_deduplicator_skip_media.py` (1/1 通过)
- **关键场景测试**:
    - 图片屏蔽+不同文本：第一条发送成功（文本模式）。
    - 相同图片+相同文本：第二条被文本去重拦截（预期行为）。
    - 相同图片+不同文本：第二条发送成功（仅文本，去重跳过媒体签名，确认不重复）。

## 质量矩阵 (Quality Matrix)
- [x] 代码风格符合规范
- [x] 逻辑覆盖全面 (Media/Text combinations)
- [x] 单元测试覆盖核心链路
- [x] 无回归风险
