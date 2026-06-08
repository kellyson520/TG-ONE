# 🚀 工业级动态优先级与公平调度方案 (QoS 3.0: Fair & Dynamic)

## 1. 核心痛点与目标
解决单纯固定优先级带来的"邻居干扰"与"突发流量"问题：
1.  **同级竞争 (Noisy Neighbor)**: 100 个普通群，其中 1 个群刷屏 (Spam)，导致其他 99 个正常群的消息被堵塞。
2.  **流量突发 (Bursty Traffic)**: 平时安静的群突然爆发（如突发新闻），如何既保证其响应，又不让其彻底淹没系统？
3.  **真正的动态调整**: 优先级不能是静态的，必须根据**实时拥塞程度**自动浮动。

## 2. 核心算法: 拥塞感知优先 (Congestion-Aware Priority, CAP)

引入 **CAP 动态评分公式**:
> **`FinalPriority = BasePriority - (CongestionFactor × PendingCount)`**

*   **BasePriority**: 基础优先级 (由 `/vip` 或 Config 设定，如 50, 10)。
*   **PendingCount**: 该群组在队列中**当前待处理**的消息数量。
*   **CongestionFactor**: 拥塞惩罚因子 (例如 0.5)。

### 2.1 场景模拟 (Simulation)
假设 **普通群 A (Live)** 和 **刷屏群 B (Spam)** 基础优先级均为 **10**。
1.  **群 B** 瞬间涌入 100 条消息：
    *   第 1 条: P = 10 - (0 * 0.5) = **10**
    *   第 20 条: P = 10 - (19 * 0.5) = **0.5**
    *   第 100 条: P = 10 - (99 * 0.5) = **-39.5** (极低优)
2.  **群 A** 此时发送 1 条消息：
    *   第 1 条: P = 10 - (0 * 0.5) = **10**
3.  **调度结果**:
    *   Worker 会先处理群 B 的前几条，然后立刻转向群 A 的新消息（P=10 > P=0.5）。
    *   **效果**: 实现了 **加权公平队列 (Weighted Fair Queuing)**，任何群组都无法独占资源。

## 3. 架构设计 (Architecture)

### 3.1 内存层：智能优先级队列 (Smart Priority Queue)
*   **组件**: `services/queue_service.py`
*   **数据结构**:
    *   `self.queue`: `asyncio.PriorityQueue`
    *   `self.pending_counts`: `Dict[chat_id, int]` (实时计数器)
*   **流程**:
    1.  **Enqueue**: 
        *   查表获取 `chat_id` 当前排队数 `N`.
        *   计算 `P_final`.
        *   `pending_counts[chat_id] += 1`.
        *   `queue.put((-P_final, timestamp, item))`.
    2.  **Dequeue (Worker)**:
        *   `item = queue.get()`.
        *   `pending_counts[item.chat_id] -= 1`.

### 3.2 交互层：指令化管理 (ChatOps)
*   **指令**: `/set_priority <level>` (不变)。
*   **新增**: `/queue_status`
    *   显示当前 Top 10 拥塞群组及其被惩罚后的有效优先级。
    *   方便管理员监控"谁在堵塞系统"。

### 3.3 边界处理与复杂业务 (Boundary Handling)
1.  **VIP 群组的特权**:
    *   VIP 群 (Base=50) 的惩罚因子可以更低 (例如 0.1)，或者其 Base 足够高，即使积压 100 条 (50 - 5 = 45)，依然高于普通群 (10)。
    *   **结论**: VIP 依然享有插队权，但 VIP 互搏时，公平原则生效。
2.  **极度积压 (Deep Backlog)**:
    *   若某群组 Pending > 1000，触发 **熔断保护 (Circuit Breaker)**，直接拒绝入队或丢弃旧消息（可配置），防止 OOM。
3.  **冷群突发**:
    *   平时不发消息的群，Pending=0，突发的第一条消息必定享受最高 BasePriority，响应极快。

## 4. 实施计划 (Implementation Plan)

### Phase 1: 基础建设 (Foundation)
*   [ ] 重构 `QueueService`:
    *   引入 `PriorityQueue`。
    *   引入 `pending_counts` 字典 (利用 `defaultdict(int)`).
    *   实现线程安全的计数器增减。

### Phase 2: 动态算法 (The Algorithm)
*   [ ] 实现 CAP 公式: `calculate_priority(base, chat_id)`.
*   [ ] 集成到 `enqueue` 方法。
*   [ ] 配置化因子: 支持在 `config.yaml` 或环境变量调整 `CONGESTION_PENALTY_FACTOR` (默认 0.2)。

### Phase 3: 指令与监控 (Ops)
*   [ ] 实现 `/vip` (设置 BasePriority).
*   [ ] 实现 `/queue_status` (查看实时拥塞/惩罚情况).

### Phase 4: 压力与边界测试 (Validation)
*   [ ] **Test 1 (Spam vs Normal)**: 模拟群 A 发 500 条，群 B 发 1 条。验证 B 是否在 A 处理完之前被处理。
*   [ ] **Test 2 (VIP vs Spam)**: 模拟 VIP 刷屏。
*   [ ] **Test 3 (Retention)**: 验证计数器在异常 Crash 下的准确性 (也可接受轻微误差，因为 Key 会自动过期或复位).

## 5. 收益总结
| 场景 | 旧方案 (Fixed QoS) | 新方案 (Fair Dynamic QoS) |
| :--- | :--- | :--- |
| **群 A 刷屏** | 堵死普通群 B | 群 A 优先级自动衰减，群 B **秒级插队** |
| **VIP 刷屏** | 堵死普通 VIP | VIP 内部公平竞争，不影响顶级 Admin |
| **系统稳定性** | 易被单点流量打垮 | **流量隔离**，单点故障不扩散 |

**复用与兼容**: 
完全复用现有的 `RuleRepo` 存储配置，仅在内存层 (Service) 增加计数逻辑，**对数据库零侵入**，**对现有业务零破坏**。
