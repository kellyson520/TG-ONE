# Mock API Server for Frontend Development

## 背景 (Context)
开发前端时，为了避免每次都连接真实的 Telegram 客户端（启动慢、网络依赖、日志干扰），我们需要一个 "Mock Mode"。
该模式仅启动 FastAPI Server，并使用模拟的 Telegram Client 对象来“欺骗”后端依赖，使其能够正常提供 API 服务。

## 待办清单 (Checklist)

### Phase 1: Mock Server Script
- [x] 创建 `scripts/mock_telegram_client.py`: 实现 `TelegramClient` 的最小集 Mock 类
    - [x] `start()`
    - [x] `get_me()`
    - [x] `iter_messages()`
    - [x] `get_messages()`
    - [x] `disconnect()`
    - [x] `is_connected()`
- [x] 创建 `scripts/run_mock_server.py`: 启动脚本
    - [x] 加载配置
    - [x] 初始化 Mock Clients
    - [x] 注入 Container
    - [x] 启动 FastAPI Server (`uvicorn`)
- [x] 验证 Web Admin 是否可访问 (http://localhost:9000)

### Phase 2: Data Mocking (Optional/Later)
- [ ] 实现 `iter_messages` 返回假数据，以便测试历史记录功能
