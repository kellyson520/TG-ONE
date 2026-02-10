# 修复 Container RuntimeError 及 Dedup 指纹记录失败

## 背景 (Context)
系统在关闭时出现 `AttributeError: 'Container' object has no attribute 'event_bus'`，导致预关闭广播发送失败。
同时，去重引擎在处理特定 ChatID (如 `3198337360`) 时记录消息指纹失败。

## 待办清单 (Checklist)

### Phase 1: 问题诊断
- [ ] 分析 `core/bootstrap.py` 中 `Container` 对象的结构及 `event_bus` 的初始化与销毁时机。
- [ ] 分析 `services/dedup/engine.py` 中指纹记录失败的原因（可能与大整数或类型有关）。

### Phase 2: 核心修复
- [ ] 修复 `Container` 缺失 `event_bus` 属性的问题（增加安全检查或修正初始化顺序）。
- [ ] 修复去重引擎记录指纹失败的问题。

### Phase 3: 验证
- [ ] 运行相关单元测试。
- [ ] 模拟关闭流程验证广播修复。
- [ ] 验证大数值 ChatID 的指纹记录。
