# 任务: 修复 Web 页面记录详情未知与任务列表获取失败

## 背景 (Context)
用户报告 Web 管理界面存在两个关键 Bug：
1. 记录详情显示为 "Unknown" (未知)。
2. 获取任务列表失败（可能导致页面加载转圈或报错）。

## 策略 (Strategy)
1. **Bug 1 (未知详情)**: 
    - 检查 `AnalyticsService.search_records` 的预加载逻辑。
    - 统一使用 `RuleDTOMapper.log_to_dict` 进行数据转换，确保名称解析逻辑一致。
    - 补全缺失的 `joinedload`。
2. **Bug 2 (任务列表失败)**:
    - 修复 `stats_router.py` 中对 `created_at` 等字段直接调用 `.isoformat()` 可能导致的 `AttributeError`（当字段为字符串时）。
    - 增加鲁棒的日期格式化处理。

## 待办清单 (Checklist)

### Phase 1: 故障分析与重现
- [x] 代码分析：确定 `search_records` 缺失预加载
- [x] 代码分析：定位 `get_tasks_list` 的日期处理漏洞

### Phase 2: 修复方案实施
- [x] 修复 `AnalyticsService.search_records`: 补充预加载并优化数据返回格式
- [x] 修复 `stats_router.py`: 优化任务列表日期格式化逻辑
- [x] 检查 `web_admin/mappers/rule_mapper.py` 是否有其他遗漏

### Phase 3: 验证与验收
- [x] 运行针对性单元测试 (`tests/unit/services/test_analytics_service.py`)
- [x] 验证 `search_records` 的输出包含正确的 Source/Target 名称
- [x] 验证任务列表接口在混合日期格式下不报错

### Phase 4: 闭环与归档
- [x] 更新 `process.md`
- [x] 生成 `report.md`
