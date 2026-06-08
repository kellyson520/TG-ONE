# 交付报告：修复版本信息翻页显示

## 摘要 (Summary)
修复了机器人输出版本信息时展示全部日志的问题。通过将 `SystemMenu` 中的版本信息展示对接至已有的分页逻辑，并简化 `WELCOME_TEXT` 欢迎语内容，实现了输出的精简化与交互化。

## 架构变更 (Architecture Refactor)
- **UI/UX**: `SystemMenu.show_version_info` 现在调用 `changelog_callback.show_changelog` 提供的分页组件。
- **Data Truncation**: `version.py` 中的 `WELCOME_TEXT` 现在仅包含最新版本的更新概要，旧版本日志需通过 `/changelog` 或菜单分页查看。

## 验证结果 (Verification)
- [x] 语法检查：`python -m py_compile` 通过。
- [x] 逻辑审计：`/changelog` 和菜单中的分页按钮回调均已在 `callback_router` 中注册。
- [x] 路径验证：`SystemMenu` 到 `show_changelog` 的导入路径正确。

## 用户操作指南 (Manual)
- 输入 `/start` 或开启机器人时，将看到简洁的最新更新记录。
- 在 `菜单 > 会话管理 > 帮助与版本 > 版本信息` 中，现在可以点击“下一页”查看历史日志。
- 直接输入 `/changelog` 也可以进入分页日志界面。
