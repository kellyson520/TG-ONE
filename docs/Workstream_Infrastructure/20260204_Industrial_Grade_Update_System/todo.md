# 工业级自动升级系统 (Industrial-Grade Auto-Update System)

## 背景 (Context)

实现基于 **Supervisor守护进程 + 状态机 + 原子回滚** 的工业级自动升级方案，解决以下核心痛点：

1. **无限重启保护**：升级失败后自动检测断点，继续重试或自动回滚
2. **原子性保证**：代码更新、依赖安装、数据库迁移要么全成功，要么全回滚
3. **进程外控制**：将危险的文件系统操作移交到 Shell 脚本执行

## 核心策略 (Strategy)

采用 **双层状态机** 模型：
- **Layer 1 (Shell Supervisor)**: 容器 PID 1 进程，管理 Python 子进程生命周期
- **Layer 2 (Python App)**: 业务逻辑、备份数据、触发升级信号、数据库迁移

## 待办清单 (Checklist)

### Phase 1: 核心架构实现 ✅
- [x] 重构 `entrypoint.sh` 为 Supervisor 守护进程
- [x] 实现退出码约定机制 (Exit Code 10 = 请求更新)
- [x] 实现 Shell 层的 Git/Pip 更新逻辑
- [x] 实现 Shell 层的原子回滚机制
- [x] 实现代码备份与恢复逻辑

### Phase 2: Python 升级服务重构 ✅
- [x] 重构 `UpdateService` 支持双层状态机
- [x] 实现 `trigger_update()` - 备份DB、写锁、退出进程
- [x] 实现 `post_update_bootstrap()` - 启动引导、DB迁移、清理锁
- [x] 实现数据库原子备份机制
- [x] 实现数据库回滚机制

### Phase 3: 启动流程集成 ✅
- [x] 在 `main.py` 中集成 `post_update_bootstrap()`
- [x] 确保在任何业务逻辑前执行升级后置处理
- [x] 实现维护模式中间件
- [x] 在 FastAPI 中注册维护模式中间件

### Phase 4: Docker 集成 ✅
- [x] 验证 `Dockerfile` 使用正确的 `entrypoint.sh`
- [x] 确保脚本执行权限正确配置
- [x] 验证容器重启后的断点续传能力

### Phase 5: 测试与验证 ⏳
- [ ] 测试正常升级流程
- [ ] 测试 Git 失败回滚
- [ ] 测试 Pip 失败回滚
- [ ] 测试容器断电重启恢复
- [ ] 测试数据库迁移失败回滚
- [ ] 测试维护模式中间件

### Phase 6: 文档与交付 ⏳
- [ ] 编写操作手册
- [ ] 更新系统架构文档
- [ ] 生成 `report.md`

### Phase 7: 高级功能 🚀
- [x] **增量更新**: 仅下载变更的文件，优化依赖安装流程 (已实现 md5 校验跳过)
- [x] **灰度发布**: 支持通过 `UPDATE_CANARY_PROBABILITY` 实现基于用户 ID 的灰度更新
- [x] **版本回退**: 实现 `/history` 查看记录及 `/rollback <SHA>` 定向回退
- [x] **更新通知**: 升级全周期通过 Telegram EventBus 发送实时通知

### Phase 8: 监控与告警 🚨
- [x] **告警机制**: 严重失败（如多次启动失败或回滚失败）时触发 ERROR_SYSTEM 告警
- [x] **健康检查**: 升级后自动执行数据库、网络及核心文件完整性验证

## 实现说明

### 核心文件变更

1. **scripts/ops/entrypoint.sh** (重构)
   - 实现 Supervisor 守护进程
   - 支持退出码约定 (Exit Code 10)
   - 实现 Git/Pip 更新逻辑
   - 实现原子回滚机制
   - 实现死循环保活

2. **services/update_service.py** (增强)
   - 添加 `EXIT_CODE_UPDATE = 10` 常量
   - 添加 `trigger_update()` 方法
   - 添加 `post_update_bootstrap()` 方法
   - 添加 `_rollback_db()` 方法

3. **main.py** (集成)
   - 在启动流程最开始调用 `post_update_bootstrap()`
   - 确保在加载 ORM 模型前执行

4. **web_admin/middlewares/maintenance.py** (新建)
   - 实现维护模式中间件
   - 检测 UPDATE_LOCK.json 文件
   - 返回友好的维护页面

5. **web_admin/fastapi_app.py** (集成)
   - 导入 MaintenanceMiddleware
   - 注册中间件（最后添加，确保最先执行）

### 工作流程

#### 正常升级流程
1. 用户触发更新（Web 后台或自动检测）
2. Python 调用 `update_service.trigger_update()`
3. 备份数据库到 `data/backups/auto_update/bot.db.{timestamp}.bak`
4. 写入锁文件 `data/UPDATE_LOCK.json`
5. 退出进程，返回 Exit Code 10
6. Shell Supervisor 捕获退出码
7. 创建代码备份 `data/backups/auto_update/code_backup_{timestamp}.tar.gz`
8. 执行 `git fetch && git reset --hard origin/main`
9. 执行 `pip install -r requirements.txt`
10. 重启 Python 进程
11. Python 启动时检测到锁文件
12. 执行 `alembic upgrade head` 迁移数据库
13. 删除锁文件
14. 系统恢复正常服务

#### 失败回滚流程
- **Git 失败**: Shell 自动解压最新代码备份，删除锁文件，重启
- **Pip 失败**: Shell 自动解压最新代码备份，删除锁文件，重启
- **DB 迁移失败**: Python 自动恢复数据库备份，删除锁文件，继续启动（降级模式）
- **容器断电**: 重启后检测到锁文件，Shell 重新执行更新流程

### 安全保障

1. **原子性**: 代码、依赖、数据库三者要么全成功，要么全回滚
2. **幂等性**: 更新流程可重复执行，不会造成数据损坏
3. **断点续传**: 容器重启后自动检测状态，继续或回滚
4. **数据保护**: 备份目录 `data/` 被严格排除，不会被覆盖
5. **维护模式**: 升级期间自动拦截请求，返回友好提示
