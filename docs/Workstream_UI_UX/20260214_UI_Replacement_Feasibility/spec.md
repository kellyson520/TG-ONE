# UI 替换技术方案 (UI Replacement Specification)

## 1. 架构目标
将现有的 Jinja2 服务端渲染架构替换为 React 现代化单页应用 (SPA) 架构。
- **前端**: React 19 + Vite + Tailwind + Zustand (源自 `Kimi_Agent_电报控制台UI/app`)
- **后端**: FastAPI (保持现有接口，必要时进行适配)

## 2. 关键变更点

### 2.1 前端适配
- **API 通信**: 创建 `src/lib/api.ts`，使用 `axios` 封装后端接口调用，处理 JWT Token。
- **状态管理**: 扩展 `Zustand` Store，从后端初始化真实数据，而非使用 Mock 数据。
- **跨域 (CORS)**: 开发环境下配置 Vite Proxy，生产环境下由 FastAPI 静态托管。

### 2.2 后端适配
- **静态托管**: 修改 `fastapi_app.py`，将根路径 `/` 指向 React 的 `index.html`。
- **API 对齐**: 
    - 确保 `/api/stats/overview` 等接口返回的数据结构符合 `src/types/index.ts` 的定义。
    - 如果结构不一致，在 `web_admin/mappers` 中增加适配层。
- **认证迁移**: 统一使用 `Authorization: Bearer <token>` 头部进行鉴权。

## 3. 目录结构调整
- 原 `web_admin` 保持为后端逻辑。
- 在 `web_admin/frontend` (新建) 存放 React 源代码。
- `web_admin/dist` 存放 React 构建产物。

## 4. 实施步骤

### 第 1 阶段: 后端接口审计与增强
- [ ] 审计 `stats_router.py` 返回值与前端 `StatsOverview` 类型是否匹配。
- [ ] 审计 `rule_crud_router.py` 返回值与前端 `Rule` 类型是否匹配。
- [ ] 在 FastAPI 中新增跨域支持 (已存在，需确认)。

### 第 2 阶段: 前端代码迁移与调试
- [ ] 将 React 源代码移动至 `TG ONE/web_admin/frontend`。
- [ ] 配置 `vite.config.ts` 的 `proxy` 指向 `http://localhost:8000` (FastAPI 默认端口)。
- [ ] 实现 `src/lib/api.ts` 并替换 `Dashboard.tsx` 中的 Mock 数据。

### 第 3 阶段: 构建与部署方案
- [ ] 编写构建脚本。
- [ ] 更新 `fastapi_app.py` 挂载 `dist` 目录。
- [ ] 验证全链路流程。

## 5. 风险点
- **WebSocket 兼容性**: 现有的日志推送是基于特定 WebSocket 格式的，前端需要按照协议连接。
- **认证失效**: 需要确保刷新页面后 Token 仍然有效（利用 Zustand Persist）。
