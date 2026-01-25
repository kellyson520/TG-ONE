# 全链路单元测试覆盖计划 (Full Link Unit Testing Plan)

## 🎯 目标
完善单元测试覆盖率，确保系统核心模块（Filters, Middlewares, Utils, Core）均有测试用例守护。目标是消除未测试的 Blind Spots。

## 📝 任务列表 (Test Coverage Checklist)

### 1. 🔍 过滤器模块 (Filters) [P0]
- [ ] 创建 `tests/unit/filters/` 目录
- [ ] **Core Logic**: 测试 `FilterChain` (执行顺序、中断处理)
- [ ] **Duplicate Filter**: 测试 `DuplicateFilter` (去重逻辑、数据库交互 Mock)
- [ ] **Content Filters**: 测试 `TextFilter`, `MediaFilter` (关键词匹配、正则匹配)
- [ ] **Security Filters**: 验证 `SecurityFilter` (恶意文件拦截)

### 2. 🛡️ 中间件模块 (Middlewares) [P1]
- [ ] 创建 `tests/unit/middlewares/` 目录
- [ ] **Sender Middleware**: 测试 `SenderMiddleware` (消息发送、重试、错误处理)
- [ ] **RateLimit Middleware**: 测试流控逻辑

### 3. 🔧 核心组件 (Core Components) [P1]
- [ ] **Pipeline Execution**: 完善 `Pipeline.execute` 测试
- [ ] **Event Bus**: 验证 `EventBus` 的订阅与分发

### 4. 🛠️ 工具库 (Utils) [P2]
- [ ] **Time Range**: 验证 `utils.helpers.time_range`
- [ ] **Entity Validator**: 验证 `utils.helpers.entity_validator`
- [ ] **Smart Dedup**: (Complexity High) 基础逻辑测试 `SmartDeduplicator`

## 🚀 执行策略
1. 为每个模块创建独立的测试文件 `test_{module_name}.py`。
2. 广泛使用 `unittest.mock` (`AsyncMock`, `MagicMock`) 隔离外部依赖（尤其是 DB 和 Telegram Client）。
3. 确保测试运行速度快（避免 `sleep`，使用 mock complete）。

## 📊 验证
- 运行 `pytest` 生成覆盖率报告。
