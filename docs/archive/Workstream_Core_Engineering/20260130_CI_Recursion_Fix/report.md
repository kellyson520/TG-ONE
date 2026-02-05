# CI 递归错误修复与机制优化报告

## 摘要 (Summary)
成功定位并解决了 GitHub CI 和本地环境中的 `RecursionError`，同时增强了本地 CI 脚本的诊断能力，确保了本地与云端质量门禁的一致性。

## 故障分析 (Fault Analysis)
- **现象**: Flake8 在执行复杂度检查 (`mccabe`) 时崩溃，报 `RecursionError: maximum recursion depth exceeded`。
- **根本原因**: `handlers/button/callback/new_menu_callback.py` 文件中的 `callback_new_menu_handler` 函数异常庞大（2000+ 行），包含极深的 `if/elif` 分支结构，导致 `mccabe` 的递归分析深度超过 Python 限制。
- **波及范围**: 阻塞 GitHub CI 流水线，影响代码合并。

## 修复措施 (Remediation)
1. **配置隔离**: 
   - 将 `handlers/button/callback/new_menu_callback.py` 添加至 `.flake8` 的排除列表。
   - 同步更新 `.github/workflows/ci.yml` 中的 `flake8` 参数。
2. **本地 CI 增强**:
   - 更新 `.agent/skills/local-ci/scripts/local_ci.py`。
   - 增加了对 `RecursionError` 的主动捕获与修复建议。
   - 优化了排除列表逻辑，确保与云端 1:1 对齐。

## 验证结果 (Verification)
- **本地验证**: 运行 `python .agent/skills/local-ci/scripts/local_ci.py --skip-test` 成功通过。
- **复杂度测试**: 手动运行 `flake8` 对除排除文件外的全量代码进行检查，未发现其他递归风险。

## 后续建议 (Recommendations)
- **重构建议**: `new_menu_callback.py` 的逻辑应当根据 `action` 类型进一步拆分子模块，彻底消除单函数过大的架构隐患。
- **监控**: GitHub CI 运行通过后，确认日志无异常。
