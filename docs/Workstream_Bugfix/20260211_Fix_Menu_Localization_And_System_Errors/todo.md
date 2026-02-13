# 任务: 修复菜单面板、汉化转发详情及系统导入错误

## 背景 (Context)
用户反馈菜单面板中转发详情缺失（AttributeError），部分界面无法关闭，转发热度趋势需要汉化，且系统服务中存在由于 `cleanup_old_logs` 缺失导致的导入错误。

## 核心路径 (Strategy)
1.  **Menu Fix**: 在 `MenuController` 中补全 `show_forward_analytics` 方法。
2.  **UI Localization**: 修改 `AnalyticsService` 或相关的 Renderer，将英文指标汉化为中文。
3.  **UI Interaction**: 检查无法关闭的界面，补全关闭回调或按钮。
4.  **Core Fix**: 检查 `models.models`，确认 `cleanup_old_logs` 是否被移除或更名，并修复 `system_service` 的导入。

## 待办清单 (Checklist)

### Phase 1: 故障诊断 (Diagnostic)
- [ ] 验证 `MenuController` 中 `show_forward_analytics` 的缺失情况
- [ ] 定位汉化目标文件（可能是 `services/analytics_service.py` 或 `ui/renderers/analytics_renderer.py`）
- [ ] 验证 `models.models` 中 `cleanup_old_logs` 的状态
- [ ] 调研"界面无法关闭"的具体场景

### Phase 2: 方案同步 (Setup)
- [ ] 更新 `docs/process.md` 状态

### Phase 3: 编码实现 (Build)
- [ ] 在 `MenuController` 中实现 `show_forward_analytics`
- [ ] 汉化转发详情及趋势指标
- [ ] 修复 `system_service` 导入错误 (`cleanup_old_logs`)
- [ ] 修复无法关闭的菜单界面

### Phase 4: 质量门禁 (Verify)
- [ ] 运行 `pytest tests/unit/controllers/test_menu_controller.py` (若存在)
- [ ] 静态代码检查 `flake8`
- [ ] 手动验证 (如果环境允许)

### Phase 5: 最终交付 (Report)
- [ ] 生成 `report.md`
- [ ] 更新 `process.md` 为 100%
- [ ] 清理临时文件
