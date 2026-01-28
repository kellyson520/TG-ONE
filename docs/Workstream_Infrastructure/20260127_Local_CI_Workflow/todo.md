# Task: 建立本地 CI 技能与工作流

## Context
目标是将"编写完成代码 -> 本地 CI 验证 -> 云端 CI 推送"这一流程标准化与自动化。
避免用户直接运行全量测试，同时确保推送前代码符合 `core-engineering` 规范。

## Todo List
- [x] **Init**: 创建 `local-ci` 技能定义 (SKILL.md) <!-- id: 1 -->
- [x] **Script**: 编写/整理一键检查脚本 `scripts/local_ci.py` (整合 arch_guard, flake8, bandit) <!-- id: 2 -->
- [x] **Test**: 验证脚本是否符合资源限制 (2GB RAM) <!-- id: 3 -->
- [x] **Workflow**: 创建 `/ship` 工作流文件 <!-- id: 4 -->
- [x] **Docs**: 更新 `AGENTS.md` 注册新技能 <!-- id: 5 -->

## Definition of Done
1. 存在 `.agent/skills/local-ci/SKILL.md`
2. 存在 `.agent/workflows/ship_code.md`
3. 用户输入 `/ship` 即可触发完整检查与提交流程。
