# Menu System Audit and Refactor

## 背景 (Context)
用户反馈在重构过程中菜单系统缺失了许多功能。需要对 `NewMenuSystem` 及其子模块进行全面审计，修复缺失的方法和不一致的逻辑。

## 待办清单 (Checklist)

### Phase 1: 现状审计
- [ ] 审计 `handlers/button/new_menu_system.py` 中的调度逻辑
- [ ] 审计 `handlers/button/modules/` 下的所有模块，寻找未实现的方法 (`NotImplementedError`) 或空置的跳转
- [ ] 检查与 `forward_management.py`, `settings_manager.py` 等旧模块的集成情况
- [ ] 运行 grep 寻找可能的 `AttributeError` 风险点（如调用了不存在的子模块方法）
- [x] 修复旧版回调处理器 `TypeError` (解决 5 参数不匹配问题) <!-- id: 5 -->
- [x] 修复 `ForwardManager` 中 `_load_global_settings` 缺失导致的 `AttributeError` <!-- id: 6 -->
- [x] 补全 `NewMenuSystem` 对 `AnalyticsMenu`, `RulesMenu`, `SystemMenu` 的所有代理方法 <!-- id: 7 -->
- [x] 统一 `rule_detail_settings` 的新旧菜单入口 <!-- id: 8 -->

### Phase 2: 模块功能补全 & 交互优化
- [ ] 补全 `analytics_menu.py` 中的缺失统计逻辑
- [ ] 补全 `filter_menu.py` 与规则过滤器的联动
- [x] 补全 `rules_menu.py` 中的规则编辑功能 (多源详情、同步配置、运行状态占位) <!-- id: 9 -->
- [x] 补全 `system_menu.py` 中的系统管理指令 <!-- id: 10 -->
- [ ] 优化 `SearchCallbackHandler` 与 `NewMenuSystem` 的整合
- [ ] 实现 `SystemStatus` 的实时数据采集

### Phase 3: 架构对齐
- [ ] 确保所有菜单模块遵循 `BaseMenuHandler` (如果存在)
- [ ] 统一按钮回调协议 (`new_menu:{action}:{params}`)
- [ ] 修复循环引用风险

### Phase 4: 验证与报告
- [ ] 运行相关的单元测试
- [ ] 在 Bot 环境中模拟常用点击流
- [ ] 生成详细报告
