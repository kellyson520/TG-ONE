# 日志审计漏洞全面修复 (AppLog Audit Full Fix)

## 背景 (Context)
2026-03-18 日志审计暴露 3 大 P0/P1 性能阻断漏洞：
1. `HotwordService.flush_to_disk` 自学习嵌套 IO → 刷写耗时 180s+
2. `TelegramAPIOptimizer.get_chat_statistics` 超时 chat_id 无熔断 → 堵堆信号量
3. `get_users_batch` 在批处理中串行 `get_entity` → 假批量真单步

## 待办清单 (Checklist)

### Phase 1: HotwordService 智能自适应噪声学习解耦
- [x] `flush_to_disk` 中保留候选词累积，移除同步加载 global_day JSON 的逻辑
- [x] 新增 `_noise_accumulator: Dict[str, int]` 持久跨周期存储候选词计数
- [x] 新增 `_noise_learning_lock` 防止重入，新增 `_last_noise_learn_time` 时间戳
- [x] 新增 `_global_day_cache` (tuple: data,ts) 缓存 10 分钟，防止多次触发重复读盘
- [x] 实现三级触发条件: Burst(单词 >30次) / HighVol(总词数 >40) / Timeout(>30min 兜底)
- [x] `_noise_learning_job()` 以 `asyncio.create_task` 后台异步运行，不阻塞 flush
- [x] 单元测试更新以适配新的异步触发机制

### Phase 2: API 超时负反馈熔断器
- [x] 在 `TelegramAPIOptimizer` 中添加 `_negative_cache: Dict[str, float]`
- [x] 在 `get_chat_statistics` 中，超时触发后写入负反馈缓存（TTL 120s）
- [x] 在 `get_entity` 前先检查负反馈缓存，命中则直接跳过

### Phase 3: get_users_batch 真批量修复
- [x] 替换循环内单步 `get_entity` 为 `get_input_entity` 利用本地缓存
- [x] 加入异常捕获并跳过，去除循环内 `await asyncio.sleep(0.01)` 造成堆积

### Phase 4: 验证与归档
- [ ] `python -m py_compile` 静态验证三个文件
- [ ] 生成 `report.md`
- [ ] 更新 `process.md`
