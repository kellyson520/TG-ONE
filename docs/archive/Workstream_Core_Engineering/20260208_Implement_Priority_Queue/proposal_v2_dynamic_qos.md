# 🚀 工业级动态优先级系统升级方案 (QoS 2.0) 建议书

## 1. 核心目标 (Objectives)
将现有的静态优先级机制升级为**动态、自动化、可交互**的工业级 QoS (服务质量) 系统。
解决核心痛点：
1.  **人工配置繁琐**：通过聊天指令直接管理。
2.  **处理拥塞**：在内存层面实现真正的 "VIP 插队" (PriorityQueue)，而非仅仅依赖数据库排序。
3.  **防止饥饿**：引入动态老化权重 (Dynamic Aging)，防止低优先级任务在高峰期永久由于积压而被遗忘。

## 2. 架构设计 (Architecture)

### 2.1 交互层：指令化管理 (ChatOps)
实现 Telegram 交互指令，支持管理员直接调整当前会话优先级。

*   **指令**: `/set_priority <level>`
    *   *别名*: `/vip`, `/p`
*   **参数映射**:
    *   `critical` / `100`: **最高级 (系统运维/紧急)** - 立即执行 + 独占线程资源
    *   `high` / `vip` / `50`: **高优先级 (付费/重要群组)** - 优先于普通消息
    *   `normal` / `10`: **默认** - 实时消息
    *   `bulk` / `0`: **低优先级** - 历史导入/积压数据
*   **交互示例**:
    > **User**: `/set_priority vip` (在群组 A 中)
    > **Bot**: ✅ **配置已更新**
    > 群组 [A] 优先级已提升至 **High (50)**。系统缓存已刷新，即刻生效。

### 2.2 内存层：真·优先级队列 (In-Memory Priority Queue)
目前 `queue_service` 使用 `asyncio.Queue` (FIFO)。在内存积压（例如 500 条待处理）时，高优先级消息仍需排队。
**升级方案**:
*   替换为 **`asyncio.PriorityQueue`**。
*   **数据结构优化**: `QueueItem = Tuple[Priority (Negated), Timestamp, Payload]`
    *   使用 `Priority * -1` 确保 Python 最小堆优先弹出最大优先级。
    *   引入 `Timestamp` 确保同优先级下 FIFO（先进先出）。
*   **效果**: 哪怕内存中积压了 10,000 条普通消息，新的 VIP 消息进入后，Worker 下一次 `get()` **必定** 取出该 VIP 消息。**延迟 < 1ms**。

### 2.3 调度层：动态老化 (Dynamic Aging / Starvation Protection)
防止低优先级任务在海量 VIP 流量下被"饿死"。

*   **机制**: 在 Worker 获取任务时计算动态权重。
*   **公式**: `DynamicPriority = BasePriority + (WaitTime_Minutes * 0.5)`
*   **实现**: 
    - 既然我们使用 DB `fetch_next`，可以在 SQL 查询中加入时间权重（权重较低，避免破坏 VIP 体验）。
    - 简单方案：每 10 分钟运行一次 `Rescue` 任务，将被积压超过 1 小时的任务临时提升优先级。

## 3. 实施计划 (Implementation Plan)

### Phase 1: 交互指令与注册 (User Command & Registration) - [关键]
*   **实现**: 创建 `handlers/priority_handler.py`。
    *   **指令模式**: `/set_priority`, `/vip`, `/p`。
    *   **上下文逻辑**: 
        *   **在群组/频道中**: 目标 = 当前聊天。 (`/vip 100`) -> 自动检测该聊天的规则。
        *   **在私聊中 (Bot)**: 目标 = 规则 ID + 等级。 (`/vip 12 100`) -> 将规则 #12 设置为优先级 100。
        *   **UX 优化**: "规则 ID" (代号) 比 Chat ID 更容易记忆。用户可以在 Web UI 或通过 `/list_rules` 找到规则 ID。
        *   **缺少目标**:如果在私聊中且未提供目标 -> 回复用法指南: "❌ 私聊用法: /vip <rule_id> <priority>"
    *   **验证**: 
        1.  解析参数。
        2.  验证用户管理员权限。
        3.  调用 `RuleService.update_rule(chat_id, priority=val)`。
        4.  回复确认信息。
*   **注册 (至关重要)**: 
    *   **文件**: `services/bot/handler_service.py`。
    *   **动作**: 注册匹配模式的处理程序: `^/(set_priority|vip|p)(?:\s+(.+))?$`.
    *   **验证**: 利用现有的系统命令加载日志。
*   **边界情况**:
    *   用户非管理员 -> 回复 "权限被拒绝"。
    *   聊天未绑定规则 -> 为新 VIP 群组自动创建规则以确保立即生效。

### Phase 2: 内存优先级队列 (Memory Priority Queue) - [核心]
*   **重构**: `services/queue_service.py`。
*   **复用**: 保持 `MessageQueueService` 类结构。
*   **变更**: 
    *   `self.queue = asyncio.PriorityQueue(maxsize=...)`。
*   **项目结构**:
    *   为 `QueueItem` 定义 `@dataclass(order=True)`。
    *   字段: `priority: int` (最小堆取反: -100 < -10), `timestamp: float`, `payload: Any`。
    *   **逻辑**: `enqueue` 方法必须接受 `priority` 参数 (默认 0)。
    *   **消费者**: `_worker_loop` 必须 `await self.queue.get()` -> `item.payload`。
*   **稳定性**:
    *   确保对项目包装器调用 `task_done()`。
    *   优雅处理 `QueueFull` 异常 (背压)。

### Phase 3: 自动化老化与防饿死 (Aging & Anti-Starvation) - [进阶]
*   **组件**: `services/scheduler_service.py`
    *   复用现有的调度器基础设施。
*   **逻辑**: 
    *   SQL 更新: `UPDATE task_queue SET priority = priority + 1 WHERE status='pending' AND created_at < NOW() - INTERVAL '10 min' AND priority < 100`.
    *   **限制**: 将现有优先级上限设为 100 (管理员级别)。
*   **注册**: 添加到 `scheduler.add_job`。

## 4. 架构一致性与代码复用 (Architecture Alignment)
*   **服务层**: 逻辑保留在 `RuleService` 和 `QueueService` 中。Handlers 是薄封装。
*   **持久化**: 利用现有的 `ForwardRule` 表 `priority` 列。无需架构迁移。
*   **依赖注入**: 使用 `core.container` 访问服务。

## 5. 预期收益与风险
| 指标 | 现状 (v1) | 升级后 (v2) |
| :--- | :--- | :--- |
| **VIP 响应延迟** | 高负载下需排队 (5s+) | **即时 (<100ms)** |
| **配置复杂度** | 需查表/API | **一键指令 (/vip)** |
| **系统鲁棒性** | 低优任务可能饿死 | **全自动防饿死 (动态老化)** |

### 风险控制
*   **内存开销**: PriorityQueue 开销可忽略不计。
*   **指令冲突**: 确保 `/set_priority` 不与其他机器人冲突 (如有需要使用显式前缀)。
*   **迁移**: 无缝。滚动更新安全。

---
**状态**: 提案已更新。准备实施。从 Phase 1 开始。
