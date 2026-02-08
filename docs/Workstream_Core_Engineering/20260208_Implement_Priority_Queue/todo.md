# 优先级队列实施方案 (QoS 4.0: 动态泳道路由)

## 🎯 核心目标
实施 **QoS 4.0 (动态泳道路由)**，通过 **流量整形 (Traffic Shaping)** 与 **物理隔离**，彻底解决消息积压与突发流量问题。

**核心理念**: 
1.  **CAP 计算 (Ingress)**: 根据基础优先级与当前拥塞程度计算动态得分。
2.  **物理分流 (Lane Isolation)**: 将消息路由至完全隔离的 FIFO 队列 (Critical/Fast/Standard)。
3.  **严格调度 (Strict Egress)**: Worker 优先清空高优先队列。

## ✅ 架构复用与对齐
-   **Config**: `RuleRepo.get_priority_map()` (现有)。
-   **Queue**: `queue_service.py` -> 升级为 **Multi-Lane FIFO (3x asyncio.Queue)** + `pending_counts`。
-   **Listener**: `message_listener.py` -> 仅传递 `BasePriority`，计算下沉至 Service。

## 📋 任务分解 (Task Breakdown)

### Phase 1: 基础设施改造 (Multi-Lane Queue) - [已完成] ✅
- [x] **QueueService重构**:
    - [x] 定义泳道常量: 
        -   `LANE_CRITICAL` (Admin/System, P>90) - 永不阻塞
        -   `LANE_FAST` (VIP/Normal, P>=50) - 业务优先
        -   `LANE_STANDARD` (Bulk/Spam, P<50) - 尽力而为
    - [x] 数据结构: 
        -   `self.lanes = { 'critical': asyncio.Queue(), 'fast': asyncio.Queue(), 'standard': asyncio.Queue() }`
        -   `self.lane_names = ['critical', 'fast', 'standard']`
    - [x] 初始化:
        -   移除旧的 `self.queue` (PriorityQueue).
        -   初始化新的 `pending_counts = defaultdict(int)`.
    - [x] 辅助方法:
        -   `qsize()`: 返回所有泳道总和。
        -   `empty()`: 检查所有泳道是否为空。

### Phase 2: 动态路由与拥塞感知 (Ingress Router) - [已完成] ✅
- [x] **Enqueue逻辑**:
    - [x] **CAP 算法实现**: 
        -   `current_pending = self.pending_counts[chat_id]`
        -   `score = base_priority - (current_pending * CONGESTION_PENALTY_FACTOR)`
    - [x] **Router (分流器)**: 
        -   If `score >= 90` -> `lanes['critical'].put()`
        -   Elif `score >= 50` -> `lanes['fast'].put()`
        -   Else -> `lanes['standard'].put()`
    - [x] **状态维护**:
        -   `self.pending_counts[chat_id] += 1`
        -   记录 Metrics: `ingress_fast`, `ingress_downgrade`.
- [x] **配置化**: 
    -   添加 `CONGESTION_PENALTY_FACTOR` (默认 0.5) 到 `QueueService` 类属性或配置。

### Phase 3: 严格优先调度 (Strict Priority Egress) - [已完成] ✅
- [x] **Worker Loop**:
    - [x] **Strict Priority Fetch (Event-Based)**:
        -   Worker Logic:
            1.  `await self._newItemEvent.wait()`
            2.  `self._newItemEvent.clear()`
            3.  Inner Loop (While `qsize() > 0`):
                -   `if critical: get_nowait()`
                -   `elif fast: get_nowait()`
                -   `elif standard: get_nowait()`
                -   `else: break`
        -   **Benefit**: Zero CPU usage when idle, instant wake-up for high priority.
    - [x] **Signal Logic**:
        -   In `params` or `put`: `self._newItemEvent.set()` to wake up workers.
    - [x] **Task Done**:
        -   `self.pending_counts[item.chat_id] -= 1` (原子操作)
        -   `lane.task_done()`
    - [x] **Anti-Starvation**: 
        -   CAP 算法天然保证了 **Fast Lane 不会被永远占满** (刷屏者分数降低后被路由到 Standard)。

### Phase 4: 用户指令交互 (Ops) - [已完成] ✅
- [x] **PriorityHandler**:
    - [x] `/set_priority <level>` (Alias `/vip`): 设置 BasePriority (影响初始路由)。
        -   支持 `me`, `chat_id`, `rule_id`。
    - [x] `/queue_status`: 
        -   显示各泳道积压深度: `Critical: 0 | Fast: 5 | Standard: 1520`
        -   显示 Top 5 拥塞群组。
- [x] **注册**: 在 `handlers/bot_handler.py` 中注册指令。

### Phase 5: 验证与测试 (Validation) - [已完成] ✅
- [x] **Test 1: 物理隔离 (Isolation)**: 
    -   模拟 VIP A 刷屏 (500条) -> 验证 A 被降级到 Standard。
    -   模拟 VIP B 发送 1 条 -> 验证 B 进入 Fast 且被优先处理。
- [x] **Test 2: 性能 (Overhead)**: 
    -   全速压测，验证 CPU 开销低于 v3 (无排序操作)。
- [x] **Test 3: 计数器 (Consistency)**: 
    -   验证 `pending_counts` 在异常 (Worker Crash) 后的一致性 (或增加定期重置机制)。

## 📅 历史记录
-   **Phase 1 (v1)**: 基础优先级计算 (Listener层) [已完成] ✅
