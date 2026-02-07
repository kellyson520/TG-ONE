# 20260207_Hotfix_Sync_And_UI_Fixes

## 背景 (Context)
用户反馈了四个主要问题：
1. 消息转发时，虽然是刚发送，却被去重引擎判定为“命中时间窗口 (Time window hit)”。
2. 部分菜单平面的“关闭”按钮无响应。
3. 菜单主页面不显示“节省流量 (Savings)”统计数据。
4. “会话消息去重”功能无法正常扫描到重复消息或执行删除。

## 策略 (Strategy)
- **Time Window**: 检查 `core/services/dedup_service.py` 中的时间戳比对逻辑，排查时区差异或逻辑偏移（如 `abs(diff) < threshold` 是否写反或阈值配置有误）。
- **UI Buttons**: 检查 `handlers/button/callback/callback_handlers.py` 及相关 `menu` 类，核对 `close` 回调的 `pattern` 匹配。
- **Savings Data**: 检查 `MainMenuView` 的数据绑定，确认 `statistics_repo` 是否正确回传了 `savings` 字段。
- **Session Dedup**: 审计 `handlers/button/modules/dedup.py` (或相关模块)，检查 Telegram API 扫频逻辑及权限。

## 待办清单 (Checklist)

### Phase 1: 时间窗口与去重逻辑修复
- [x] 审计 `core/services/dedup_service.py` 逻辑
- [x] 审计 `core/repositories/dedup_repo.py` 存储逻辑
- [x] 修复时区或逻辑比对错误
- [x] 编写测试用例验证去重时间窗口判定

### Phase 2: UI 异常修复 (Close & Savings)
- [x] 修复菜单主页面“节省流量”不显示的问题
- [x] 修复各个菜单页面“关闭”按钮无法响应的错误
- [x] 全量审计所有一级菜单的闭环回调

### Phase 3: 会话去重功能修复
- [x] 审计 `会话管理 > 会话去重` 后端实现
- [x] 修复官方 API 搜索扫描失效问题
- [x] 修复删除消息逻辑执行失败问题
- [x] 模拟扫描并验证去重效果

### Phase 4: 验证与验收
- [x] 执行本地 CI 门禁
- [x] 提交修复报告
- [x] 更新 `process.md`
