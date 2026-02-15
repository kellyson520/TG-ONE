# Web UI 真实数据接入 (Real Data Integration)

## 背景 (Context)
目前 Web 面板 (Web Admin) 的部分页面 (如 Logs, Dashboard 等) 仍在使用硬编码的 Mock 数据。本任务旨在移除所有前端示例数据，全面对接后端真实 API，确保数据实时性和准确性。

## 待办清单 (Checklist)

### Phase 1: 审计与发现 (Audit & Discovery)
- [x] 扫描前端代码，识别所有 Mock 数据使用点 (e.g., `Logs.tsx`, `Dashboard.tsx`)
- [x] 确认后端 API 是否已存在对应接口 (查阅 `api/` 目录或 Swagger)
- [x] 若后端接口缺失，记录需求并创建后端开发子任务 (Task Control, Dashboard Charts)

### Phase 2: 后端接口适配 (Backend API Adaptation)
- [x] 创建或修改后端 Endpoint 以支持前端需求 (Task Pause/Resume/Delete, Stats)
- [x] 确保 API 返回数据格式符合前端组件要求
- [x] 验证 API 鉴权与性能
- [ ] 后端增加 Dashboard 图表所需聚合数据 (Traffic Trend, Message Types)

### Phase 3: 前端数据接入 (Frontend Integration)
- [x] 重构 `Logs.tsx` 使用真实 API
- [x] 重构 `Tasks.tsx` 使用真实 API (支持 Pause/Resume)
- [x] 重构 `Downloads.tsx` 使用真实 API
- [x] 重构 `Security.tsx` 使用真实 API
- [x] 重构 `Archive.tsx` 使用真实 API
- [ ] 重构 `Dashboard.tsx` (图表与活动日志仍为 Mock)
- [ ] 移除 `src/mocks` 或相关硬编码数据文件
- [x] 增加错误处理 (Error Handling) 和加载状态 (Loading State)

### Phase 4: 验证与验收 (Verification)
- [ ] 本地运行验证所有页面数据加载正常
- [ ] 检查控制台无相关报错
