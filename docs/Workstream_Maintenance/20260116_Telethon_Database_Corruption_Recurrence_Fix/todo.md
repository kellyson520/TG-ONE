# Telethon 会话数据库损坏修复 (Recurrence)

## 背景 (Context)
用户报告 `quchong-bot` 出现 `database disk image is malformed` 错误，导致 Telethon 更新循环崩溃并断开连接。
根据日志，错误发生在 `telethon/sessions/sqlite.py` 的 `process_entities` 中。
虽然之前有过类似修复，但问题再次出现，需彻底排查病根并修复。

## 技术策略 (Strategy)
1. **深度诊断**: 检查 `user.session` 和 `bot.session` 的完整性。
2. **安全备份**: 对所有会话文件进行离线备份。
3. **彻底修复**: 
    - 停止相关容器（防止并发写导致再次损坏）。
    - 尝试使用 SQLite 的 `.recover` 或重建机制。
    - 如果损坏严重，删除 `Entity` 表（Telethon 丢失实体缓存会重新从 API 获取，比重做 Session 好）。
4. **预防机制**: 审查代码中是否有并发初始化 Client 的行为。

## 待办清单 (Checklist)

### Phase 1: 故障诊断与备份
- [x] 验证本地 SQLite 文件状态 (已执行 `integrity_check`)
- [ ] 创建会话文件备份
- [ ] 检查进程列表，确认是否有多个实例在运行

### Phase 2: 数据库修复
- [ ] 尝试使用 Python 脚本执行 `VACUUM` 或 `.recover` 逻辑
- [ ] 如果 `entities` 表损坏，清理该表
- [ ] 验证修复后的数据库完整性

### Phase 3: 恢复与验证
- [ ] 重启容器/服务
- [ ] 监控日志，确认 `process_entities` 错误消失
- [ ] 验证 Bot 基本功能（转发、菜单）

### Phase 4: 根因预防
- [ ] 检查 `main.py` 或启动逻辑中的 Client 初始化
- [ ] 确保单一 Session 文件不被多进程共享写
