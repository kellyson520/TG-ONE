# 配置审计与环境标准化 (Phase 1)

## 背景 (Context)
项目目前存在散落的 `os.getenv` 和 `os.environ` 调用，违反了架构白皮书中的“配置统一”原则。需要将所有配置项归口至 `core.config.settings`，并确保 `.env` 模板完整。

## 待办清单 (Checklist)

### Phase 1: 扫描与分析
- [x] 扫描全项目 `os.getenv` 和 `os.environ` 的使用情况。
- [x] 识别主要违规文件：`other_callback.py`, `backup.py`, `db_maintenance_service.py`, `settings_applier.py`。
- [x] 识别脚本中的特例并决定是否归并。

### Phase 2: 配置收拢 (核心逻辑)
- [x] 替换 `handlers/button/callback/other_callback.py` 中的 `os.getenv`。
- [x] 替换 `services/db_maintenance_service.py` 中的 `os.getenv`。
- [x] 替换 `services/settings_applier.py` 中的 `os.environ` 设置为对 `settings` 的直接修改。
- [x] 替换 `repositories/backup.py` 中的 `os.environ.get`。
- [x] 替换 `scripts/` 目录下相关脚本的配置获取方式 (`database_health_check.py`, `trace.py`, `sqlite_to_postgres.py` 等)。
- [x] **RSS 模块配置归口**：移除 `web_admin/rss/core/config.py`，统一使用全局 `settings`。

### Phase 3: 环境标准化
- [x] 补充 `.env` 模板文件，涵盖所有新增项。
- [x] 更新 `Settings.validate_required()` 增加必要的强校验。
- [x] 移除 `core/helpers/env_config.py` (已废弃)。

### Phase 4: 验证
- [x] 运行核心功能测试，确保配置加载正常。
- [x] 运行本地 CI，检查是否有新的架构违规。
