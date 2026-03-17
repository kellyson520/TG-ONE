# 20260317_Audit_Risk_Fixes
审计高危风险排查与修复

## 背景 (Context)
在 20260317 深度审计中，发现了 `smart_buffer` 缺乏背压控制（P0 风险）、`hotword_service` 并发竞态（P1 风险）以及 SimHash 拦截树暴力清空面临防守真空的漏洞（P1 风险），需立即安全修复。

## 策略 (Strategy)
1. 给 `SmartBufferService` 增加缓冲 Bounded limits 溢出阻断。
2. 将 `HotwordService` 的拦截网重置逻辑升级为 LRU (滑动淘汰) 模型。
3. 给 `ACManager` 读写状态进行线程锁加固。
4. 清理 `handlers/user_handler.py` 中的残余调试 `print`。

## 待办清单 (Checklist)

### Phase 1: 缓冲背压防护 (P0 核心修复)
- [x] 1. 修复 `services/smart_buffer.py`: 设定最大缓冲 contexts 总量，溢出抛异常拦截。

### Phase 2: 可靠性加固升级 (P1 级修复)
- [x] 2. 修复 `services/hotword_service.py`: 拦截网由暴力清空改为滑动平稳淘汰。
- [x] 3. 审查/加固 `core/algorithms/ac_automaton.py` 或全局 `ACManager` 并发读写锁。

### Phase 3: 卫生打扫与验证 (P2 / Finalize)
- [x] 4. 清理 `handlers/user_handler.py` 的调试 `print` 残留。
- [x] 5. 简单运行相关模块验证安全性，生成 `report.md`。

