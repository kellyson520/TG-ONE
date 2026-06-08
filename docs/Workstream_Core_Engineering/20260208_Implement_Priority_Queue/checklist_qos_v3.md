# 动态 QoS 3.0 (拥塞感知优先) 实施清单

## 🎯 核心目标
实施 **CAP 算法 (Congestion-Aware Priority)**，解决"邻居干扰"与"突发流量"问题。
**公式**: `P_final = Base - (Pending * Factor)`。

## ✅ 架构复用与对齐
-   **Config**: `RuleRepo.get_priority_map()` (现有)。
-   **Queue**: `queue_service.py` -> 升级为 `PriorityQueue` + `pending_counts`。
-   **Listener**: `message_listener.py` -> 仅传递 `BasePriority`，**实际计算下沉到 QueueService** 以保证实时性。

## 📋 任务分解 (Task Breakdown)

### Phase 1: 队列核心升级 (Core)  
- [ ] **QueueService重构**:
    - [ ] 引入 `self.pending_counts = defaultdict(int)`。
    - [ ] 升级 `self.queue` -> `asyncio.PriorityQueue`。
    - [ ] 定义 `QueueItem(priority, timestamp, payload)` (dataclass, total_ordering)。
- [ ] **Enqueue逻辑**:
    - [ ] 实现 `calculate_priority(base, chat_id)`。
    - [ ] 在 `put` 前自增计数器。
    - [ ] 在 `task_done` 后自减计数器。
- [ ] **配置化**:
    - [ ] 添加 `CONGESTION_PENALTY_FACTOR` (默认 0.5)。

### Phase 2: 用户指令交互 (Ops)
- [ ] **PriorityHandler**:
    - [ ] 实现 `/set_priority <level>` (更新 BasePriority)。
    - [ ] 实现 `/queue_status` (显示前 10 个拥塞群组)。
- [ ] **注册**:
    - [ ] 在 `bot/handler_service.py` 中注册。

### Phase 3: 边界保护 (Robustness)
- [ ] **熔断机制**:
    - [ ] 如果某群组 Pending > 1000 -> 拒绝入队 / 丢弃最老消息。
    - [ ] 记录 "Drop Metrics"。
- [ ] **防饿死 (Aging)**:
    - [ ] （可选）如果使用了 CAP，低优任务会自动随着高优任务处理完毕而提升相对位置吗？
        -   其实 PriorityQueue 静态排序后，Position 固定。
        -   但新任务进不来高位。旧任务如 P=-50，会被新任务 P=10 插队。
        -   **老化策略**: 定期扫描队列（或双队列设计），提升滞留任务权重。
            -   *简化方案*: 暂时依赖 CAP 的自然消耗，因为高积压会导致新任务优先级降低(P=-100)，从而让旧任务(P=-50)有机会被处理。**CAP 天然具有防饿死特性！** (拥塞越严重，新任务优先级越低，旧任务相对变高)。

### Phase 4: 验证与测试 (Validation)
- [ ] **Test 1: 公平性**: 模拟 A 群(500 msg) vs B 群(1 msg)。B 必须插队。
- [ ] **Test 2: VIP 优先**: 模拟 VIP 群刷屏 vs 普通群刷屏。
- [ ] **Test 3: 计数器准确性**: 确保 `pending_counts` 在异常下不泄露（最终一致性）。

## 📅 进度
- [ ] **Phase 1** (Queue Core)
- [ ] **Phase 2** (Commands)
- [ ] **Phase 3** (Robustness)
- [ ] **Phase 4** (Verify)
