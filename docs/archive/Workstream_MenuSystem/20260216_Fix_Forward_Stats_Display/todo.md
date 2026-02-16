# Task: 修复转发统计与节省流量显示 (Fix Forward Stats & Saved Traffic Display)

## 1. 背景 (Background)
用户反馈转发管理中心中的“节省流量”显示为 0.0 MB，且需要确保相关统计数据能够正确采集和展示。
目前发现去重中间件拦截消息时未记录节省的流量。

## 2. 目标 (Objectives)
- [x] 在 `dedup_service.py` 中记录已拦截消息的流量大小。
- [x] 在 `middlewares/dedup.py` 中传入 `rule_id` 以便按规则统计拦截数。
- [x] 增强 `analytics_service.py` 的数据聚合逻辑，包含 `saved_traffic_bytes`。
- [x] 在 `MainMenuRenderer` 的各个 Hub 视图中增加“拦截流量”显示。
- [x] 修复 `forward_recorder.py` 中文本消息大小计算为 0 的问题。

## 3. 方案设计 (Spec)
### 3.1 统计采集
- 修改 `DeduplicationService.check_and_lock`：当检测到重复时，调用 `_on_duplicate_found`。
- `_on_duplicate_found` 负责：
    - 更新 `ChatStatistics.saved_traffic_bytes`。
    - 更新 `RuleStatistics.filtered_count`。
    - 记录状态为 `filtered` 的 `RuleLog`。

### 3.2 数据链路
- `forward_service.get_forward_stats` 从 `analytics_service` 提取今日 `saved_traffic_bytes`。
- `realtime_stats_cache` 同步缓存更新后的数据。

### 3.3 UI 展现
- `MainMenuRenderer.render_forward_hub`: 增加“拦截流量”项。
- `MainMenuRenderer.render_analytics_hub`: 增加“拦截流量”项，并优化布局。

## 4. 进度记录 (Todo)
- [x] 实现在 `dedup_service` 中采集统计数据
- [x] 调整中间件调用链路
- [x] 更新分析服务的数据聚合
- [x] 更新渲染器的 Hub 视图
- [x] 修复文本消息大小计算 bug
- [x] 验证统计看板数据正确性
