# 联网更新功能实现

## 背景 (Context)
为 TG ONE 添加自动/手动联网更新功能，提升维护效率。

## 策略 (Strategy)
基于 `git` 实现本体更新，配合 `GuardService` 实现自动重启。

## 待办清单 (Checklist)

### Phase 1: 基础设施
- [x] 在 `core/config/__init__.py` 增加更新配置项
- [x] 创建 `services/update_service.py` 基础骨架
- [x] 在 `.env` 中添加默认更新配置

### Phase 2: 核心功能
- [x] 实现远程版本检测逻辑 (GitHub API 或 Raw version.py)
- [x] 实现 `git reset --hard` 原子更新逻辑 (参考成熟方案)
- [x] 实现网络连通性预检逻辑
- [x] 实现 `requirements.txt` 差异检测与依赖自动同步
- [x] 实现定期检查后台任务
- [x] 增强 `guard_service` 重启逻辑 (支持 Windows/Unix 物理重启、延时释放锁)
- [x] 实现回滚保护机制 (Rollback)

### Phase 3: 命令集成
- [x] 在 `handlers/commands/system_commands.py` 添加 `/update` 命令
- [x] 添加 `/rollback` 指令
- [x] 在 `/status` 命令中增加版本更新提示

### Phase 4: 验证与优化
- [x] 编写模拟更新测试 (已集成逻辑验证)
- [x] 验证 Windows 环境下的 `os.execl` 重启可靠性
- [x] 记录详细更新日志
