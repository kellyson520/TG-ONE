# 去重引擎 v4 迭代与边界覆盖 (Upgrade Deduplication Engine v4)

## 背景 (Context)
当前的去重引擎 (v3) 已经实现了基于策略模式的分布式检测，集成 SimHash、LSH Forest 和 SSH v4 视频哈希。
为了进一步提升检测精度并覆盖更多边界场景（如跨会话去重、小文本精确匹配、多语言支持），需要进行 v4 版本的迭代。

## 核心策略 (Strategy)
- **全局扩散检测 (Cross-Chat Detection)**: 增加 L0/L1 级别的全局指纹检索，检测在不同频道出现的相同内容。
- **自适应阈值算法 (Adaptive Similarity)**: 基于文本长度动态调整 SimHash 判定阈值，减少短文本误判。
- **P-Frame 视频增强**: 引入关键帧特征采样，提升长视频和压缩视频的识别率。
- **多语言分词预处理**: 优化 CJK (中日韩) 文本的 SimHash 数据质量。
- **边界鲁棒性提升**: 针对空内容、超大视频、媒体组 (Album) 进行专项优化。

## 待办清单 (Checklist)

### Phase 1: 方案设计与审核
- [x] 编写详细技术升级方案 (`spec.md`)
- [x] 提交用户审核并获取反馈

### Phase 2: 核心组件升级 (Iteration)
- [x] 优化 `tools.py` 支持更细粒度的文本清洗与 CJK 分词
- [x] 实现 `Adaptive Threshold` 算法
- [x] 扩展 `SmartDeduplicator` 支持全局检索 (scope=global)
- [x] 补充表情包过滤设置 (`StickerStrategy`)

### Phase 3: 边界场景覆盖 (Boundary Coverage)
- [x] 优化 `VideoStrategy` 对超大/超小视频的差异化处理 (SSH v5)
- [x] 实现媒体组 (Grouped ID) 的聚合摘要去重 (`AlbumStrategy`)
- [x] 增加零长度文字/空媒体的兜底保护
- [x] 实现配置持久化与懒加载 (`load_config`)

### Phase 4: 验证与交付 (Verification)
- [ ] 性能压力测试 (LSH 全局查询延迟)
- [ ] 单元测试覆盖新增边界用例
- [x] 优化初始化日志，增加策略链透明度
- [ ] 生成升级报告并归档
