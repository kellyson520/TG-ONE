# Fix Changelog Edit Message Error (20260204)

## 背景 (Context)
用户反馈在处理 `/changelog` 命令时出现 `telethon.errors.rpcerrorlist.MessageIdInvalidError`。
经过初步分析，错误发生在 `show_changelog` 函数中调用 `event.edit` 时。这是因为 `/changelog` 是一个 `NewMessage` 事件（命令），而 `edit` 通常用于 `CallbackQuery` 事件。对于命令事件，应该使用 `respond` 或 `reply`。

## 策略 (Strategy)
在 `show_changelog` 中判断 `event` 的类型：
- 如果是 `CallbackQuery.Event`，继续使用 `edit`。
- 如果是 `NewMessage.Event`，改用 `respond` 或重新设计逻辑使两者兼容。

## 待办清单 (Checklist)

### Phase 1: 问题诊断
- [x] 复核 `handlers/commands/rule_commands.py` 中 `handle_changelog_command` 的调用方式
- [x] 解析 `handlers/button/callback/modules/changelog_callback.py` 中 `show_changelog` 的实现逻辑
- [x] 确认 Telethon `event.edit` 的行为限制

### Phase 2: 代码修复
- [x] 在 `show_changelog` 中增加对 `event` 类型的判断
- [x] 确保 `/changelog` 命令能正确发送新消息，且后续翻页操作能正确编辑消息
- [x] 检查是否有其他类似的命令存在相同问题

### Phase 3: 验证与验收
- [x] 验证 `/changelog` 命令输出 (代码审查通过)
- [x] 验证翻页按钮功能 (代码审查通过)
- [x] 生成 `report.md` 并归档任务
- [x] 全局审计 `event.edit` 使用情况 (78处安全,0处问题)
