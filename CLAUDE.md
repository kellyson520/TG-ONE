# CLAUDE.md — TG-ONE 项目行为约束

## 约束规则（必须遵守）

### ❌ 禁止操作
1. **禁止本地构建 Docker 镜像** — 不要运行 `docker build`、`docker-compose build` 或任何构建镜像的命令
2. **禁止跑压力测试** — 不要运行 locust、wrk、ab 或任何负载/压力测试工具
3. **禁止跑全量测试** — 不要运行 `pytest tests/` 不带路径参数的全量执行

### ✅ 允许操作
1. **代码审查** — 读取和分析代码，找出 bug 和改进点
2. **单模块测试** — 只运行特定模块的测试，如 `pytest tests/path/to/specific_test.py`
3. **文档更新** — 更新 README、CHANGELOG、CLAUDE.md 等文档
4. **代码修复** — 修改代码修复具体 bug，提交 commit 并关闭对应 issue

### 工作流程
1. 阅读 issue 描述，理解问题
2. 定位相关代码文件
3. 运行**单个失败测试**确认问题：`pytest tests/path/to/test.py::TestClass::test_method -v`
4. 修复代码
5. 再次运行**同一个测试**确认修复
6. 提交 commit：`git commit -m "fix: 简短描述 (closes #N)"`
7. 关闭 issue：`gh issue close N`
