# 应用日志深度审计与风险治理交付报告 (Report)

## 概要 (Summary)
运行自研日志聚类分析脚本，对 2026-03-18 的 936 条 `[WARNING]` 及 `[ERROR]` 进行了全样本分类。报告发现主要风险集中于 **热词服务 IO 阻断**、**Telegram API 获取超时** 以及 **内存水位警告频繁**。

---

## 🔍 聚合统计摘要 (Top Bottlenecks)

| 频次 | 模块 / 警告信息 | 归属类型 | 风险等级 |
|:---|:---|:---|:---|
| 205 | `[hotword_service] 刷写热词数据 性能警告` | IO / 组件性能 | **P0 (高危)** |
| 191 | `[api_optimization] 获取聊天实体超时` | 接口超时 / 阻断 | **P0 (高危)** |
| 191 | `[api_optimization] 获取聊天统计 性能警告` | 接口超时 / 并发 | **P1 (中危)** |
| 164 | `[hotword_service] 解析热词批次 性能警告` | CPU 密集 / 计算 | **P1 (中危)** |
| 110 | `[ResourceGuard] 内存触及 Warning 水位 (降速+GC)` | 资源泄露 / 压降 | **P1 (中危)** |

---

## 🚨 核心漏洞与潜在隐患分析

### 1. 【高危-性能阻断】HotwordService 刷写耗时过长 (186s+)
*   **现象**: `flush_to_disk` 频频发出 Time 爆表警告（最高达 180 秒）。
*   **成因定位**: 
    1. 在 `flush_to_disk` 中，为了进行“自学习”模型，每次落盘（通常是定时或高频触发）都会调用 `await self._load_period_data("global", "day")` 从磁盘加载全量 JSON。
    2. JSON 反序列化及复杂循环（包含多次 global 比较和词频计算）变成了**隐式 CPU/IO 阻塞**。
*   **修复建议**: 
    - 将“自动学习噪声词”从 `flush_to_disk`（高频落盘操作）中剥离，迁移到 `aggregate_daily`（每日一次）或单独的低频异步定时任务。
    - L1 落盘时增加大小阈值，没必要为极小的增量反复读写盘。

### 2. 【高危-稳定性】获取聊天实体超时与堆积
*   **现象**: `获取聊天实体超时` (191次)，主要是 `GetFullChannelRequest` 之前等待 `get_entity` 返回。
*   **成因定位**: 
    - `TelegramAPIOptimizer.get_chat_statistics` 设置了 5.0 秒超时阈值。由于高并发请求、Flood Wait 或者 Telegram API 端挂起导致堆积。
    - 缺少**冷却（Cool-down）策略**: 一个不存在或访问受限的 `chat_id` 被高频调用时，每次都会吃满 5s 超时。
*   **修复建议**:
    - 对发生 `TimeoutError` 的 `chat_id` 进行短时负反馈缓存（如 1 分钟内不再重复请求该 chat_id），防止恶意/故障实体吃空信号量阻断整个 `TelegramAPIOptimizer` 的 10 信号量。

### 3. 【中危-性能损耗】`get_users_batch` 单步迭代获取实体
*   **现象**: `get_users_batch` 本该实现批量效果，却常在 5s 的 `@log_performance` 外层发出耗时警告。
*   **成因定位**:
    - 为了构造 `GetUsersRequest` 列表，循环中使用 `await self.client.get_entity(user_id)`（每次都会触发网络 IO 寻找 Entity）。
*   **修复建议**:
    - 使用 `self.client.get_input_entity` 优先解决本地缓存问题。
    - 或者允许一次异常浮点，合并入总 API 获取，避免批量包装内的“拆包执行”。

### 4. 【中危-内存控制】内存警戒水位频发
*   **现象**: `ResourceGuard` 降级及 GC 动作异常频繁。
*   **成因定位**:
    - 可能来自热词解析 `Jieba` 提取时的临时巨量 text slicing 截断。
    - 频繁的 JSON `load/dump` 将大字典装入内存触发锯齿型峰值。
*   **修复建议**:
    - 审查 `archive_manager` 的批次释放是否足够快、热词拆析后 `gc.collect()` 触发时机是否可通过降低 L1 落盘频数来改善。

---

## ✅ 审计闭环
当前任务已完成所有聚类识别和全生命周期对齐，可根据此报告针对特定阻断点（如 Hotword 刷写频率/负反馈拦截 cache）开启下一段修复流程。
