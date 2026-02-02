# 修复编排失败错误 (Fix Orchestration Failure)

## Context
用户报告部署时出现 `unknown docker command: "compose ONE/docker-compose.yml"` 错误。
确认生产环境使用 **1Panel** 面板进行编排部署。
日志显示编排任务名称为 `[TG ONE]`。

## Root Cause Analysis
1Panel 在调用 docker compose 时，内部使用的路径拼接或命令构建逻辑未能正确处理编排名称中的**空格** (`TG ONE`)。
导致 `docker` 命令接收到的参数被错误分割或截断（例如 `TG` 被吞或作为独立参数，导致后续路径 `ONE/docker-compose.yml` 解析异常）。

## Solution Strategy
1.  **Workaround**: 在 1Panel 中将编排/应用名称重命名为不含空格的格式（如 `TG_ONE`）。
2.  **Documentation**: 记录此限制，防止后续复发。

## Checklist

### Phase 1: Diagnosis & Fix
- [x] 定位错误来源 (1Panel + Space in Name)
- [x] 验证修复方案 (Advisory: Rename to `TG_ONE`)
- [x] 清理本地临时脚本

### Phase 2: Documentation
- [ ] 更新 `report.md`
- [ ] 归档
