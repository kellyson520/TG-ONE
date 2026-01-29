# 20260129_Align_Tests_With_Project_Code

## 背景 (Context)
项目代码近期进行了多次重构（如 UserRepository 增加 Telegram 登录支持，Bot Command 模块化到 submodules），现有的测试代码存在覆盖不足或逻辑不一致的问题。需要根据最新的项目代码更新测试代码，确保系统稳定性。

## 待办清单 (Checklist)

### Phase 1: UserRepository 单元测试补全
- [x] 验证 `UserRepository` 中新增的 `get_user_by_telegram_id`
- [x] 验证 `UserRepository` 中新增的 `get_admin_by_telegram_id`
- [x] 验证 `UserRepository` 中的注册开关 `get_allow_registration` / `set_allow_registration`
- [x] 验证 `UserRepository` 中的认证信息获取 `get_user_for_auth` / `get_user_auth_by_id`

### Phase 2: Bot DB Pipeline 集成测试优化
- [x] 分析 `test_bot_db_pipeline.py` 的执行死锁问题
- [x] 移除冗余的 repository mocking，使用容器内真实的 repository 配合内存数据库
- [x] 验证 `/add` 命令触发的真实数据库写入流程

### Phase 3: 全量测试验证与闭环
- [x] 运行 `pytest tests/unit/repositories/test_user_repo.py`
- [x] 运行 `pytest tests/integration/bot/test_bot_db_pipeline.py`
- [x] 运行本地 CI 确保不破坏现有逻辑
- [x] 生成任务报告 `report.md`
