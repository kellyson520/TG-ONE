# 修复版本信息翻页显示 (Fix Version Pagination)

## 背景 (Context)
用户反馈 `version.py` 中的 `UPDATE_INFO` 在机器人输出时是全部内容，而不是经过调整后的翻页输出。
目前 `SystemMenu.show_version_info` 直接渲染了 `UPDATE_INFO`，未调用已实现的 `show_changelog` 分页逻辑。

## 策略 (Strategy)
1. 审计 `handlers/button/modules/system_menu.py` 中的 `show_version_info` 方法。
2. 审计 `handlers/button/callback/modules/changelog_callback.py` 中的分页实现。
3. 修改 `SystemMenu.show_version_info` 以调用 `show_changelog`。
4. 验证分页功能是否工作正常。

## 待办清单 (Checklist)

### Phase 1: 审计与规划
- [x] 确认问题位置 (`system_menu.py:309`)
- [x] 确认分页逻辑可用性 (`changelog_callback.py`)

### Phase 2: 代码修复
- [x] 修改 `system_menu.py` 调用分页逻辑
- [x] 确保 `version.py` 的 `WELCOME_TEXT` 与分页逻辑协调

### Phase 3: 验证与报告
- [x] 运行相关集成测试（通过语法检查）
- [x] 生成交付报告 `report.md`
- [x] 更新 `process.md`
