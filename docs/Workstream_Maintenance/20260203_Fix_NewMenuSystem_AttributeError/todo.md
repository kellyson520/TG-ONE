# Fix NewMenuSystem AttributeError

## 背景 (Context)
用户报告在处理新菜单回调时出现 `AttributeError: 'NewMenuSystem' object has no attribute 'show_dedup_time_window'`。
经初步分析，`NewMenuSystem` 作为门面类，缺少了对 `SmartDedupMenu` 中部分新增方法的代理。同时 `SmartDedupMenu` 本身也缺少一些预定义的处理器。

## 待办清单 (Checklist)

### Phase 1: 核心实现
- [x] 在 `SmartDedupMenu` 中实现 `show_dedup_time_window`
- [x] 在 `SmartDedupMenu` 中实现 `show_dedup_advanced`
- [x] 在 `SmartDedupMenu` 中实现 `show_dedup_hash_examples`
- [x] 在 `NewMenuSystem` 中添加缺失的代理方法：
    - [x] `show_dedup_time_window`
    - [x] `show_dedup_statistics`
    - [x] `show_dedup_advanced`
    - [x] `show_dedup_hash_examples`

### Phase 2: 验证与清理
- [x] 验证菜单跳转是否正常
- [x] 生成任务报告
