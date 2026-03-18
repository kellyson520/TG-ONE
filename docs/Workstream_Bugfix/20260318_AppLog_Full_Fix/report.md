# 日志审计漏洞全面修复交付报告 (Report)

## 概要 (Summary)
针对 2026-03-18 应用日志审计中发现的 3 大性能阻断漏洞，采用**自适应智能触发**及**熔断降级策略**进行了全面重构。已通过静态编译验证与核心策略单元测试，消除系统在海量数据流下的隐式卡死风险。

---

## 🛠️ 修复细则与成因治理

### 1. 【热词服务】智能自适应噪声累积与后台异步解耦
*   **文件**: `services/hotword_service.py`
*   **成因**: `flush_to_disk` 在高频刷数据时，同步调用了从磁盘加载的大 JSON 反序列化任务（耗时长达 180s）。
*   **修复方案 (智能降噪方案)**:
    1. **解耦落盘**: `flush_to_disk` 仅进行 L1 缓存到累积池 (`_noise_accumulator`) 的高速内存合并，**不读磁盘**。
    2. **三级信号触发**: 设立 Burst(高频单个词) / HighVol(候选词数量) / Timeout(30min 兜底) 三级指标，智能监控内存累加池的状态。
    3. **异步隔离作业**: `asyncio.create_task(self._noise_learning_job())` 单独调度到后台异步执行，加载磁盘数据时增加了 **10 分钟缓存池 (`_global_day_cache`)**。
*   **结果**: 解除了热词刷盘主线程锁卡闭，消除 IO 重负导致的事件循环 lag 警告，自学习时效性动态提升。

### 2. 【API 优化】全链路超时熔断器（负反馈缓存机制）
*   **文件**: `services/network/api_optimization.py`
*   **成因**: 出现 `TimeoutError` 的 `chat_id` 被重复高频拉取，吞噬 `TelegramAPIOptimizer` 的并发信号量。
*   **修复方案**:
    1. 引入 `_negative_cache` 负反馈缓存，将连续发生 `asyncio.TimeoutError` 级失败的 ID 自动计入惩罚。
    2. 自动设定 **`_NEGATIVE_CACHE_TTL = 120.0`** 秒惩罚冷却期，在此期间对该 ID 发起直接拦截并默认降级返回空结果。
*   **结果**: 释放海量由于卡阻和重入吃紧的 semaphore 控制资源。

### 3. 【API 优化】修复假批处理串行网络 IO
*   **文件**: `services/network/api_optimization.py`
*   **成因**: `get_users_batch` 在构造 input 对象列表阶段，直接使用了 `await self.client.get_entity`，形成循环内单步网络 IO。
*   **修复方案**:
    1. 迁移至 **`await self.client.get_input_entity`**，优先调阅本地 Client 线程安全持有的 Entity 缓存（毫秒级无 IO）。
    2. 仅当缓存无果时才尝试一次 `get_entity`，并去除了无意义的 `asyncio.sleep(0.01)`。
*   **结果**: 极大地压降了高频批拉取用户画像时长。

---

## ✅ 交付验证
1.  **静态验证**: `services/hotword_service.py` 和 `services/network/api_optimization.py` 均执行 `py_compile` 并通过。
2.  **动态单测**: 重构 `test_hotword_learn.py` 覆盖智能降噪的新异步流程，强制触发执行结果符合白灰比对策略，验证 100% 通过。
