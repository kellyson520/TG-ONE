# 去重引擎升级方案 (Strategy Upgrade v4)

## 1. 核心算法迭代 (Algorithm Iterations)

### 1.1 自适应 SimHash 阈值 (Adaptive Thresholding)
**痛点**: 固定阈值（如 0.85）在处理超短文本（如 "转发自某频道"）时极易碰撞，在处理超长文本时可能因几个标点差异而失效。
**升级**:
- 引入 **Length-Adjusted Threshold (LAT)** 公式：
  $T(L) = \min(0.95, 0.82 + \frac{20}{L + 5})$
- L 为清洗后文本长度。
- 短文本 (10 chars): 约为 0.95 (极严格)。
- 长文本 (100 chars): 约为 0.85。

### 1.2 全局传播检测 (Global Propagation Track)
**升级**: 
- `SmartDeduplicator` 增加 `global_scope` 配置项。
- 命中全局 Bloom Filter 后，若本地库无记录，尝试查询全局持久化哈希库。
- 允许定义 "Master Chats" 指纹同步。

### 1.3 视频 SSH v5 (Enhanced Sparse-Sentinel Hash)
**升级**:
- **动态采样点**: 根据视频时长动态增加采样位置（由 5 点增加至 $\max(5, \text{duration}/60)$）。
- **色彩直方图摘要**: 抽取关键帧的色彩分布特征（低维向量），利用 Hamming 距离复核。

## 2. 边界场景覆盖 (Boundary Coverage)

### 2.1 CJK 多语言支持
- 集成简单的 `jieba` 分词（若可用）或基于 **Overlap-Ngram** 的分词算法。
- 提升中文语义重复检测的召回率。

### 2.2 相册聚类去重 (Album Clustering)
- 记录 `grouped_id`。
- 生成 "Album Fingerprint": $Hash(Sorted(ContentHashes))$。
- 若相册 80% 内容重复，则判定为重复。

### 2.3 异常输入保护
- **全空格/特殊字符文本**: 自动降级为 "Null Content"，不进入相似度计算。
- **黑屏/静音视频**: 识别特征值全 0 的哈希。

### 2.4 配置热加载与持久化 (Config Persistence)
- **动态更新**: 支持运行时调整去重阈值与开关。
- **持久化存储**: 核心配置项持久化至数据库 (`SystemConfiguration`)，重启自动恢复。
- **懒加载机制**: 首次调用时加载配置，减少冷启动延迟。

## 3. 工程实现 (Engineering)

- **最大化复用**: 
    - 维持 `BaseDedupStrategy` 合约不变。
    - 仅通过策略内部的逻辑分支出发升级。
    - 扩展 `DedupConfig` 以支持新参数。
- **性能优化**:
    - 全局检索结果通过 `PCache` 缓存 24h，减少 DB 穿透。
    - 对 Numba 优化的局部哈希算法进行预热。

## 4. 审核要点 (Review Points)
- 自适应阈值公式中参数的合理性。
- 是否需要引入外部依赖（如 jieba）。
- 全局去重的性能影响（增加了一次 Bloom 查询）。
