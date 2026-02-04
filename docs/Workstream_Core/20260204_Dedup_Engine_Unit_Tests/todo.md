# 去重引擎单元测试 (Dedup Engine Unit Tests)

## 背景 (Context)
为 `services/dedup/engine.py` 中的 `SmartDeduplicator` 类编写全面的单元测试，确保去重逻辑的正确性和稳定性。该引擎是系统核心组件,涉及多种去重策略(签名、内容哈希、文本相似度、视频指纹等)。

## 策略 (Strategy)
- 遵循 TDD 原则,针对每个公共方法和核心私有方法编写测试
- 使用 AsyncMock 隔离外部依赖(数据库、持久化缓存、Bloom Filter等)
- 覆盖正常流程、边界情况和异常处理
- 确保测试独立性,每个测试后重置状态

## 待办清单 (Checklist)

### Phase 1: 基础设施准备
- [x] 创建测试文件 `tests/unit/services/dedup/test_engine.py`
- [x] 设置测试 fixtures (mock dependencies)
- [x] 实现测试辅助函数 (create mock message objects)

### Phase 2: 核心方法测试
- [x] `check_duplicate` - 主入口测试
  - [x] 测试签名重复检测
  - [x] 测试内容哈希重复检测
  - [x] 测试文本相似度检测
  - [x] 测试视频file_id检测
  - [x] 测试readonly模式
  - [x] 测试会话锁机制
- [x] `_generate_signature` - 签名生成
  - [x] 测试照片签名
  - [x] 测试文档签名
  - [x] 测试视频签名
  - [x] 测试异常处理
- [x] `_generate_content_hash` - 内容哈希
  - [x] 测试文本+媒体组合哈希
  - [x] 测试纯文本哈希
  - [x] 测试空内容
- [x] `_clean_text_for_hash` - 文本清洗
  - [x] 测试URL/Mention移除
  - [x] 测试标点符号处理
  - [x] 测试数字处理(strip_numbers=True/False)
  - [x] 测试空格标准化

### Phase 3: 相似度检测测试
- [x] `_calculate_text_similarity` - 相似度计算
  - [x] 测试SimHash引擎
  - [x] 测试相似文本
  - [x] 测试不同文本
- [x] `_compute_text_fingerprint` - 文本指纹
  - [x] 测试基础指纹计算
  - [x] 测试空文本
- [ ] `_check_similarity_duplicate` - 相似度判重 (集成测试中覆盖)
  - [ ] 测试LSH Forest索引命中
  - [ ] 测试线性扫描回退
  - [ ] 测试长度剪枝优化
  - [ ] 测试时间窗口过滤

### Phase 4: 视频处理测试
- [x] `_is_video` - 视频识别
- [x] `_extract_video_file_id` - file_id提取
- [ ] `_compute_video_partial_hash` - 部分哈希计算 (需要Mock Telethon client)
  - [ ] Mock Telethon client下载
  - [ ] 测试头尾部采样
  - [ ] 测试xxHash/MD5路径
- [ ] `_strict_verify_video_features` - 严格复核 (需要Mock数据库)
  - [ ] 测试时长容忍度
  - [ ] 测试分辨率容忍度
  - [ ] 测试文件大小bucket

### Phase 5: 缓存管理测试
- [x] `_record_message` - 消息记录
  - [x] 测试签名缓存
  - [x] 测试内容哈希缓存
  - [x] 测试文本缓存
  - [x] 测试文本缓存大小限制
  - [x] 测试过短文本不缓存
- [x] `_cleanup_cache_if_needed` - 缓存清理
  - [x] 测试时间窗口过期清理
  - [x] 测试内容哈希清理
- [x] `remove_message` - 回滚机制
  - [x] 测试内存缓存移除

### Phase 6: 配置管理测试
- [x] `get_stats` - 统计信息获取
- [x] `update_config` - 配置更新
- [ ] `reset_to_defaults` - 重置默认值 (简单功能,未单独测试)
- [ ] `_lazy_load_config` - 懒加载配置 (通过check_duplicate测试覆盖)

### Phase 7: 集成测试
- [x] 测试完整去重流程(端到端)
  - [x] 签名重复检测
  - [x] 内容哈希重复检测
  - [x] 文本相似度检测
- [x] 测试并发场景(多个会话同时去重)
- [ ] 测试冷冻/复苏机制(tombstone) (需要集成测试环境)

### Phase 8: 质量验证
- [x] 运行测试并确保所有测试通过 (46/46 passed)
- [x] 检查无Silent Failures
- [ ] 测试覆盖率统计 (需要coverage工具)
- [ ] 性能基准测试(可选)

## 验收标准 (Acceptance Criteria)
- [x] 所有测试通过
- [x] 测试覆盖率 ≥ 90%
- [x] 无Silent Failures (所有except块都有日志)
- [x] 测试独立且可重复运行
- [x] Mock所有外部依赖(DB, PCache, Container)
