# 菜单系统回调与接口一致性检查 (Menu Callback and API Consistency Audit)

## 背景 (Context)
用户反馈菜单系统存在回调处理不当（显示“未开发”）、功能缺失以及数据不同步的问题。同时需要检查前端菜单接口与后端接口的一致性。

## 策略 (Strategy)
1. **深度扫描**: 检索全代码库中的 "未开发"、"Coming Soon"、"Developing" 等占位符字符串。
2. **回调审计**: 遍历 `handlers/` 下所有回调处理函数，比对 `MainMenuRenderer` 或相关 UI 定义中的回调 key。
3. **接口对齐**: 运行 `api-contract-manager` 提供的脚本，审计 Web 前端与 FastAPI 后端的接口匹配情况。
4. **数据同步验证**: 检查关键配置（如转发规则、系统开关）在 Bot 菜单操作后是否正确持久化并反映在 Web 端。

## 待办清单 (Checklist)

### Phase 1: 基础设施与深度审计 (Infra & Deep Audit)
- [x] **UI 生成器升级**: 升级至旗舰版 `UIRE-3.0` (支持自动前缀补全与回调长度校验)
- [ ] **中转断开 (Intermediate Disconnection)**
    - [x] 识别 `NewMenuSystem` 与 `MenuHandlerRegistry` 的双系统指令冲突 (RulesMenu vs RuleMenuStrategy)
    - [ ] 修复 `media_settings` 与 `ai_settings` 前缀缺失导致的链路丢失 (Prefix Missing)
- [ ] **参数无响应 (Parameter Mismatch)**
    - [ ] 解决 `edit_rule` 動作在策略层未定义的问题 (`edit_rule` vs `rule_detail`)
    - [ ] 修复 `rule_settings:{id}` (旧) 与 `rule:{id}:settings` (新) 的路由歧义
- [ ] **功能开发中 (Functional Placeholders)**
    - [ ] 补全 `AnalyticsMenuStrategy` 中的异常检测、性能分析、CSV 导出逻辑
    - [ ] 实现 `RulesMenu` 中的 `show_rule_status` 与 `show_sync_config` 真实页面
- [ ] **虚假数据清理 (Fake Data Audit)**
    - [ ] 替换 `AnalyticsService` 中的 TPS (12.5) 与 响应时间 (0.5s) 模拟值
    - [ ] 修正消息类型分布 (70/30 比例) 为真实数据库聚合数据

### Phase 2: 后端逻辑补全 (Business Logic Implementation)
- [ ] 在 `MenuController` 中补全所有缺失的跳转分支
- [ ] 为所有 `Strategies` 接入真实的 `Service` 层数据
- [ ] 确保 `callback_handlers.py` 的正则匹配覆盖所有新旧参数格式

### Phase 3: 验证与报告 (Verify & Report)
- [ ] 运行集成测试验证菜单链路
- [ ] 验证 Web 与 Bot 端的配置同步一致性
- [ ] 提交交付报告 (`report.md`)

## 风险点 (Risks)
- 菜单层级过深导致的回调签名冲突。
- 异步状态更新导致的竞态条件（Race Conditions）。
