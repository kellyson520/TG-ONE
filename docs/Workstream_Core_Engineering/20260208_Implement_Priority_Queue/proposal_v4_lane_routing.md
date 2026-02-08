# 🚀 工业级 QoS 4.0: 动态泳道路由与资源隔离 (Dynamic Lane Routing)

## 1. 演进思路 (Evolution)
学习 **Cisco QoS** 与 **RabbitMQ** 的成熟方案，我们发现单纯的 `PriorityQueue` (单堆) 在高并发下存在性能瓶颈（插入 $O(\log N)$）且缺乏物理隔离。
**v4 方案** 引入 **"多泳道 (Multi-Lane)"** 与 **"动态路由 (Dynamic Routing)"** 架构。

## 2. 核心架构: 动态泳道模型 (The Lanes)

不再使用单一队列，而是构建 **3 条物理隔离的 FIFO 队列** (Lanes)：

| 泳道 (Lane) | 别名 | 适用场景 | 调度权重 (Weight) | 物理隔离优势 |
| :--- | :--- | :--- | :--- | :--- |
| 🚑 **Critical** | `Emergency` | 管理员指令、系统级信号 | **100% (绝对优先)** | 永不被业务流量阻塞 |
| 🏎️ **Fast** | `VIP` | VIP 群组、高优业务 | **70% (保障带宽)** | 即使 Slow 爆满也不受影响 |
| 🚗 **Standard** | `Bulk` | 普通消息、积压数据 | **30% (尽力而为)** | 物理隔离，OOM 时可直接丢弃 |

### 2.1 动态路由算法 (Routing Algorithm)
在消息**入队 (Ingress)** 时，通过 CAP 算法动态决定该消息进入哪条泳道。

> **`Score = BasePriority - (Pending × Factor)`**

*   **Rule 1 (Admin)**: Base=100 -> Score=100 -> **Critical Lane**.
*   **Rule 2 (VIP)**: Base=50, Pending=0 -> Score=50 -> **Fast Lane**.
*   **Rule 3 (VIP Spam)**: Base=50, Pending=100 -> Score=0 -> **Standard Lane**. (VIP 刷屏自动降级!)
*   **Rule 4 (Normal)**: Base=10 -> Score=10 -> **Standard Lane**.

**✨ 核心创新**: 
*   VIP 用户**平时**走快速通道。
*   一旦 VIP 开始**刷屏**，自动被"降级/路由"到慢速通道，**物理隔离**其对其他 VIP 的影响。

## 3. 调度与防饿死 (Scheduling & Anti-Starvation)
消费者 (Worker) 不再单纯 `get()`，而是采用 **WRR (Weighted Round Robin)** 策略：

```python
# 伪代码：调度逻辑
async def get_next_task():
    # 1. 绝对优先处理 Critical
    if not critical_queue.empty():
        return await critical_queue.get()
    
    # 2. 权重调度 Fast vs Standard (7:3)
    # 每一个周期 (10次循环)
    # 7次取 Fast, 3次取 Standard
    if current_slot < 7:
        task = await fast_queue.get() or await standard_queue.get()
    else:
        task = await standard_queue.get() or await fast_queue.get()
```

## 4. 实施变更清单 (Tasks)

### Phase 1: 多级队列重构 (Infrastructure)
- [ ] **QueueService**:
    - [ ] 移除 `self.queue` (Single).
    - [ ] 新增 `self.lanes = { 'critical': Queue(), 'fast': Queue(), 'standard': Queue() }`.
    - [ ] 保持 `pending_counts` 用于 CAP 计算。

### Phase 2: 动态路由 (Ingress)
- [ ] **Enqueue**:
    - [ ] 计算 CAP Score。
    - [ ] **Router**:
        -   Score >= 90: -> `critical`
        -   Score >= 40: -> `fast`
        -   Score < 40: -> `standard`
    - [ ] 记录 Metrics: `lane_depth_critical`, `lane_depth_fast`, `lane_depth_standard`.

### Phase 3: 权重调度 (Egress)
- [ ] **Worker Loop**:
    - [ ] 实现简单的权重轮询 (或简单版：`Critical > Fast > Standard` + 偶尔强制取 Standard 防止由于 Fast 持续满载导致的完全饿死)。
    -   *成熟方案建议*: 使用 `Strict Priority` (严谨模式) 配合 `Standard` 泳道的 **TTL**。如果 Fast 满载，Standard 消息只是晚点处理，不会丢。由于我们有 CAP 降级，Fast 不会永远满载 (刷屏者会被踢出 Fast)，所以 **Strict Priority** 是安全的！
    -   *修正*: 采用 **Strict Priority** (先取 Critical, 再 Fast, 再 Standard)。
        -   **为什么安全?** 因为 CAP 算法保证了没有人能长期霸占 Fast Lane (流量整形)。

## 5. 方案对比
| 特性 | v3 (Single PriorityQueue) | **v4 (Dynamic Lane Routing)** |
| :--- | :--- | :--- |
| **性能** | 插入 $O(\log N)$ | 插入 **$O(1)** (FIFO) |
| **隔离性** | 无 (共享内存) | **强隔离** (多队列) |
| **刷屏处理** | 排序后延后处理 | **物理降级** (踢入慢车道) |
| **复杂度** | 中 | 中高 (需管理多队列) |

**结论**: v4 是真正的工业级方案，利用 **流量整形 (Traffic Shaping)** 配合 **物理隔离**，实现了性能与公平的完美平衡。
