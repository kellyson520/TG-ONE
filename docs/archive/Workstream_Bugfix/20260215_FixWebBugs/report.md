# 修复 Web 端 Bug 报告 (2026-02-15)

## 摘要 (Summary)
本次任务修复了 Web 管理系统中的一系列关键 Bug，包括统计分布显示、操作详情缺失、任务队列获取失败以及 Web 服务启动崩溃问题。

## 修复项 (Fixed Items)

### 1. 消息类型分布 "Unknown" 问题
- **原因**: 历史数据中 `message_type` 可能为 NULL，且聚合逻辑未处理空值。
- **修复**: 在 `analytics_service.py` 中添加了空值映射逻辑，并确保 `ForwardService` 在写入日志时始终包含消息类型。

### 2. 操作详情 "Unknown" 问题
- **原因**: `RuleLog` 记录时未完整填充详情字段。
- **修复**: 优化了 `forward_log_writer.py`，确保每次转发动作都记录详细的目标频道信息。

### 3. 任务队列获取失败 (500 Error)
- **原因**: `TaskQueue` 模型属性访问不一致（`retry_count` vs `attempts`），以及部分坏数据导致序列化崩溃。
- **修复**: 统一了 `stats_router.py` 中的属性访问，并增加了序列化时的异常捕获（Try-Catch），跳过损坏的任务记录。

### 4. 日志面板性能与白屏修复
- **原因**: 返回的日志文本过大或包含特殊字符导致前端渲染负担。
- **修复**: 在后端对 `message_text` 进行了长度截断（500 字符），并优化了分页查询。

### 5. 规则列表获取失败 (AttributeError)
- **原因**: DTO 定义缺失 `id` 或 `title` 字段导致 Mapper 转换失败。
- **修复**: 补全了 `KeywordDTO`, `ReplaceRuleDTO` 和 `ChatDTO` 的字段定义。

### 6. Web 服务启动崩溃 (Optional NameError)
- **原因**: `web_admin/routers/rules/rule_crud_router.py` 使用了 `Optional` 但未从 `typing` 导入。
- **修复**: 在 `rule_crud_router.py` 中添加了 `from typing import Optional`。

## 验证 (Verification)
- **单元测试**: 运行 `pytest tests/unit/web/test_rule_router.py` 全部通过。
- **服务启动**: 修复导入错误后，Web 服务可以正常加载路由。

## 归档 (Archive)
任务已闭环，所有状态已对齐。
