# 去重引擎 V4 升级报告 (Deduplication Engine V4 Upgrade Report)

## 任务概述 (Task Summary)
本项目对 TG ONE 的去重引擎进行了从 V3 到 V4 的重大升级。重点在于算法的鲁棒性、全局传播检测、特殊内容处理（表情包/相册）以及性能优化。

## 升级亮点 (Key Highlights)

### 1. 算法迭代 (Algorithm Iteration)
- **SSH v5 (Sparse-Sentinel Hash)**: 
  - 从固定5点采样升级为基于视频时长的**动态采样**（每30秒增加一个采样点，范围5-20点）。
  - 显著提升了长视频（如电影、录制视频）的查重精度，降低了碰撞率。
- **Adaptive Similarity Threshold**:
  - 文本相似度阈值不再是固定值，而是根据文本长度动态调整：`Threshold = min(0.95, 0.82 + 20 / (Length + 5))`。
  - 短文本使用高阈值防止误判，长文本维持稳定阈值确保召回。
- **CJK 深度支持**:
  - 优化了 SimHash 预处理流程，对中日韩字符进行强制分词处理，使 SimHash 在多语言环境下表现更稳定。

### 2. 全局共振检测 (Global Resonance)
- **Cross-Chat Match**: 
  - 新增 `enable_global_search` 配置。
  - 允许引擎在当前会话之外检索全局数据库，识别正在跨频道传播的热门/垃圾内容。
  - 配合 PCache 实现全局热门内容的 O(1) 级拦截速度。

### 3. 特殊内容策略 (Special Content Strategies)
- **StickerStrategy**: 
  - 针对 Telegram 表情包的 `file_unique_id` 进行独立索引和查重。
  - 支持配置是否过滤重复表情包。
- **AlbumStrategy**: 
  - 针对相册（Grouped ID）的聚合分析。
  - 通过计算相册内成员的重复比例判定整体是否属于重复转发，解决了相册部分更新或部分相同的问题。

### 4. 健壮性与边界保护
- **Zero-Length Protection**: 增加了对空消息、空媒体、特殊字符消息的兜底逻辑，防止无效索引污染数据库。
- **PCache 统一管控**: 统一了 `PersistentCacheRepository` 的过期机制 (`expire` 参数)，确保所有缓存项具有明确的时效性。
- **并发冲突防护**: 强化了会话级异步锁 (`_get_chat_lock`)，防止高并发下同一内容多次记录导致索引膨胀。
- **配置热加载**: 实现了 `DedupRepo.save/load_config`，支持运行时动态与持久化配置更新，重启后自动恢复去重参数。

## 技术参数 (Technical Specs v4)

| 参数项 | V3 实现 | V4 实现 | 说明 |
| :--- | :--- | :--- | :--- |
| 视频采样点 | 固定 5 点 | 动态 (5-20 点) | 提升长视频精度 |
| 文本阈值 | 0.85 (固定) | 0.82~0.95 (自适应) | 减少短文本误判 |
| 检索范围 | 单会话 | 全局 + 单会话 | 支持全局传播分析 |
| 配置管理 | 硬编码/环境变量 | 数据库持久化 + 懒加载 | 支持运行时动态调参 |
| 策略链顺序 | 线性 | 组合策略模式 | 优先表情包与签名检测 |
| 存储后端 | MySQL/PostgreSQL | 兼容 + Redis PCache | 性能显著提升 |

## 验证结论 (Verification)
- **单元测试**: ✅ 46+ 测试全量通过，覆盖了新加入的 `StickerStrategy`、`AlbumStrategy` 以及 `SSH v5` 核心逻辑。
- **架构审计**: ✅ 符合 DDD 分层架构，所有工具函数封装于 `tools.py`，策略逻辑高度解耦。
- **日志性能**: ✅ 完善了 `SmartDeduplicator` 的加载日志，现在能清晰显示基础设施 (Bloom/HLL/SimHash) 与所有子策略模块的加载状态，增强了系统启动时的可观测性。
- **性能评估**: 通过批处理和缓存优化，V4 引擎在高并发下对内存的占用保持在 2GB 限制内。

## 下一步建议 (Next Steps)
- 考虑引入 **LSH Forest** 进行更大规模的图像/视频特征检索。
- 增加对 Telegram "Premium" 独有媒体类型的定制去重支持。

---
**Implementation Plan, Task List and Thought in Chinese**
**Status: COMPLETED**
