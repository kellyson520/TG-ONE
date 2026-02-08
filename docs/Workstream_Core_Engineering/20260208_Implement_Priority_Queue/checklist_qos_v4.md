# 动态 QoS 4.0: 动态泳道路由 (Dynamic Lane Routing) 实施清单

## 🎯 核心理念
**CAP 计算 (Ingress) -> 物理分流 (Lane Isolation) -> 严格/权重调度 (Egress)**
通过 **Traffic Shaping (流量整形)**，将 VIP 刷屏流量物理降级到慢车道，**彻底隔离**其对其他 VIP 用户的影响。

## 📋 任务分解 (Task Breakdown)

### Phase 1: 基础设施改造 (Infrastructure) - [v4]
- [ ] **QueueService 重构 (Multi-Lane)**:
    - [ ] 定义泳道: `CRITICAL` (P>90), `FAST` (P>=50), `STANDARD` (P<50).
    - [ ] 数据结构: `self.lanes = { 'critical': asyncio.Queue(), 'fast': asyncio.Queue(), 'standard': asyncio.Queue() }`.
    - [ ] 移除旧的 `self.queue` (PriorityQueue).

### Phase 2: 动态路由 (Ingress Router) - [v4]
- [ ] **Enqueue 逻辑**:
    - [ ] 复用 CAP 算法: `score = base - (pending * factor)`.
    - [ ] **Router**:
        -   `if score >= 90: lanes['critical'].put()`
        -   `elif score >= 50: lanes['fast'].put()`
        -   `else: lanes['standard'].put()`
    - [ ] 记录 Metrics: `ingress_routing_fast`, `ingress_routing_downgrade`.

### Phase 3: 严格调度 (Strict Priority Egress) - [v4]
- [ ] **Worker Loop**:
    - [ ] 实现 **Strict Priority**:
        -   `task = get_nowait(critical) or get_nowait(fast) or await get(standard)`.
    - [ ] **Anti-Starvation**:
        -   CAP 算法天然保证了 **Fast Lane 不会被永远占满** (刷屏者分数降低后被路由到 Standard)。
        -   因此 **Strict Priority 是安全的**！无需复杂的 WRR。

### Phase 4: 用户指令交互 (Ops)
- [ ] **PriorityHandler**:
    - [ ] `/set_priority`: 设置 BasePriority (影响初始路由)。
    - [ ] `/queue_status`: 显示各泳道积压深度 (Lane Depths)。

### Phase 5: 验证与测试
- [ ] **Test 1: 物理隔离**: 
    -   VIP A 刷屏 -> VIP A 降级到 Standard。
    -   VIP B 发送 -> VIP B 保持 Fast。
    -   Worker 必须处理 B (Fast) >>> A (Standard)。
- [ ] **Test 2: 性能**: 全速压测，Standard Lane 不影响 Fast Lane 入队速度。
