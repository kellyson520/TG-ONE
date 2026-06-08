# Remove Cloud CI (移除云端 CI)

## 背景 (Context)
由于不再需要云端 CI 或为了减少外部依赖，移除 GitHub Actions 等云端 CI 配置文件。后续将完全依赖本地 CI。

## 待办清单 (Checklist)

### Phase 1: 移除配置文件
- [x] 移除 `.github/workflows/ci.yml`
- [x] 检查并移除其他可能的 CI 配置文件

### Phase 2: 验证与清理
- [x] 验证云端 CI 相关的脚本或引用是否已清理
- [x] 运行 `workspace-hygiene` 确保工作区整洁
- [x] 更新 `docs/process.md` 状态
