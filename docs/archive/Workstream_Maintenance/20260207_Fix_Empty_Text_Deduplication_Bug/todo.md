# 修复空文本消息误触智能去重 (Fix Empty Text Deduplication Bug)

## 背景 (Context)
在智能去重引擎运行过程中，若消息不含文本（如纯视频、纯图片），会导致生成的文本哈希值碰撞（空字符串哈希），从而使得所有不含文本的消息都被误判为重复并被拦截。

## 策略 (Strategy)
1. **防御性检查**: 在 `filters/keyword_filter.py` 中，在调用去重引擎前检查 `message_text`。
2. **策略降级**: 若文本为空，强制禁用 `enable_content_hash` 和 `enable_smart_similarity` 策略，仅保留媒体签名判重（若适用）。
3. **环境对齐**: 确保 `xxhash` 依赖已安装，以支持高效的哈希计算。

## 待办清单 (Checklist)

### Phase 1: 逻辑实现 (Build)
- [x] 修改 `filters/keyword_filter.py`：在 `_check_smart_duplicate` 中增加空文本检查与策略降级逻辑。
- [x] 检查 `requirements.txt`：确认 `xxhash` 是否已列入。

### Phase 2: 验证阶段 (Verify)
- [x] 检查 `xxhash` 安装情况。
- [x] 模拟发送无文本消息（如纯图片/视频），验证是否不再被错误拦截。（单元测试已验证逻辑降级）
- [x] 查看日志，确认空文本时的降级提示输出。

### Phase 3: 归档 (Report)
- [x] 生成 `report.md`。
- [x] 更新 `docs/process.md` 为已完成。
