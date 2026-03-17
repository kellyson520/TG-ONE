# 20260317_Extended_Resource_Optimization_Audit
全链路资源占用与代码减负、冗余深度审计

## 背景 (Context)
在上期底层算法审计后，需进一步拓展审查上层业务链路（如转发控制 ForwardService、任务调度 TaskService、状态会话 Session 等），重点排查常驻内存泄露隐患（如无界的 @lru_cache）、局部阻塞、以及重复解析计算的冗余。

## 策略 (Strategy)
使用静态静态正则分析和 `grep_search`，逐项盘查 **无界全局容器**、**lru_cache 常驻泄露**、以及**由于高频轮询引发的 CPU 冗余**，并生成减负优化提案。

## 待办清单 (Checklist)

### Phase 1: 内存与状态泄露审计 (Memory & Containers)
- [x] 1. 检查项目中的 **`@lru_cache`** 使用，防范 `maxsize=None` 的无界泄露。
- [x] 2. 检查 `services/` 下常驻对象的无 size 限制字典/列表 ( unbounded queues )。

### Phase 2: 代码冗余与重复计算审查 (Redundancy)
- [x] 3. 审计 `services/forward_service.py` 转发核心过滤器链路是否存有重复读库、重组文本的开销。
- [x] 4. 排除废弃或过时（Dead Code）的大块控制逻辑。

### Phase 3: 风险评估与汇总 (Assessment)
- [x] 形成审计减负汇总，写进 `report.md`。
- [x] 更新 `docs/process.md`。

