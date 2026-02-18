# 20260218_Fix_Analytics_Worker_Registry

## 背景 (Context)
用户报告了三个核心错误：
1. `ForwardRule` 对象缺少 `name` 属性（分析服务崩溃）。
2. `history_task_list` 动作在按钮策略注册表中未匹配（回调失效）。
3. Telethon `ValueError`: 无法找到特定 User ID 的输入实体（任务处理失败）。

## 技术路径 (Strategy)
1. **分析服务修复**: 检查 `ForwardRule` 模型，将错误的 `.name` 访问替换为正确的属性（如 `.description` 或 `.title`）。
2. **策略注册修复**: 在 `handlers/button/strategies/registry.py` 中寻找并注册 `history_task_list`。
3. **实体查找修复**: 在 `worker_service.py` 或 `queue_service.py` 中添加实体自动获取逻辑或增强异常处理，防止任务因缓存缺失而中断。

## 待办清单 (Checklist)

### Phase 1: 故障分析与准备
- [x] 验证 `ForwardRule` 模型属性 @Build
- [x] 验证 `analytics_service.py` 报错位置 @Build
- [x] 搜索 `history_task_list` 使用场景 @Build
- [x] 分析 Telethon 实体缺失原因 @Build

### Phase 2: 代码实现
- [x] 修复 `analytics_service.py` 中的 `AttributeError` @Build
- [x] 在注册表中补全 `history_task_list` @Build
- [x] 增强 Telethon `get_input_entity` 鲁棒性 @Build

### Phase 3: 验证与验收
- [x] 针对分析服务运行特定单元测试 @Verify
- [x] 验证按钮回调注册逻辑 @Verify
- [x] 验证 Worker 任务处理异常捕获 @Verify
- [x] 更新 `report.md` @Report
