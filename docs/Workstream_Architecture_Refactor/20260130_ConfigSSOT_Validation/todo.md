# 环境变量单一来源 (SSOT) 验证测试

## 背景 (Context)
在 Phase 1 中已完成配置项的归集，本项目现在要求所有配置必须通过 `core.config.settings` 获取。
本次任务旨在通过单元测试和静态扫描确保该“单一来源”原则在工程层面得到强制保障。

## 待办清单 (Checklist)

### Phase 1: 单元测试实现
- [x] 创建 `tests/unit/core/test_config_ssot.py`
- [x] 验证 `settings` 对象能否正确加载 `.env` 变量
- [x] 验证 `settings` 对象的必填项校验逻辑 (`validate_required`)
- [x] 验证关键变量的默认值是否符合预期

### Phase 2: 静态合规性扫描
- [x] 编写脚本/测试检查代码库中是否仍存在 `os.getenv` 或 `os.environ` 的滥用
- [x] 验证 RSS 模块是否已彻底移除本地配置依赖

### Phase 3: 验收与报告
- [x] 运行所有配置相关测试
- [x] 生成任务报告 `report.md`
- [x] 更新 `docs/process.md`
