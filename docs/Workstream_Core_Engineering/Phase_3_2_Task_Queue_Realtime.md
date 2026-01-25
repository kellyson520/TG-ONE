# Phase 3.2: 任务队列实时化 - 进度追踪

## 执行时间
开始: 2026-01-15 22:05
完成: 2026-01-15 22:10

## 任务清单

### 后端改造
- [x] 任务状态变更时触发 WebSocket 推送 (已有 EventBus 集成)
- [ ] 实现任务进度百分比计算 (需要后端支持)
- [ ] 添加任务日志流式输出 (待实施)

### 前端改造 (tasks.html)
- [x] 移除轮询逻辑 (保留 API 加载作为初始化和降级方案)
- [x] 订阅 `/ws/realtime` 的 `system` 主题
- [x] 实现任务卡片实时更新动画
- [x] 添加进度条组件 (Bootstrap Progress)
- [x] 添加连接状态指示器
- [x] 实现任务缓存机制

## 已实现功能

### 1. WebSocket 集成
```javascript
// 自动连接并订阅系统事件
function initWebSocket() {
    wsManager.connect();
    wsManager.onConnect(() => {
        wsManager.subscribe('system', handleTaskUpdate);
        showConnectionStatus(true);
    });
}
```

### 2. 实时任务更新
支持的事件类型:
- `TASK_UPDATED`: 任务信息更新
- `TASK_STATUS_CHANGED`: 任务状态变更
- `TASK_CREATED`: 新任务创建
- `TASK_COMPLETED`: 任务完成
- `TASK_FAILED`: 任务失败

### 3. 动画效果
- **状态变更动画**: 徽章闪烁效果 (500ms pulse)
- **进度条动态更新**: 平滑过渡
- **颜色渐变**: 根据进度自动调整 (0-50%: primary, 50-99%: info, 100%: success)

### 4. 进度条支持
```html
<div class="progress mt-1" style="height: 4px; width: 100px;">
    <div class="progress-bar task-progress-bar" 
         style="width: 45%" 
         aria-valuenow="45" 
         aria-valuemin="0" 
         aria-valuemax="100"></div>
</div>
```

### 5. 连接状态指示器
- 位置: 右下角固定
- 状态: 实时连接 (绿色) / 离线模式 (灰色)
- 图标: `bi-broadcast`

### 6. 降级方案
- WebSocket 不可用时自动回退到 API 轮询
- 保持完整的功能兼容性

## 使用示例

### 后端触发任务更新 (示例)
```python
from web_admin.routers.websocket_router import broadcast_system_event

# 任务状态变更
await broadcast_system_event(
    event_type="TASK_STATUS_CHANGED",
    message=f"Task #{task_id} status changed to {new_status}",
    data={
        "id": task_id,
        "status": new_status,
        "progress": 75,  # 可选
        "retry_count": 0,
        "updated_at": datetime.utcnow().isoformat()
    }
)

# 任务完成
await broadcast_system_event(
    event_type="TASK_COMPLETED",
    message=f"Task #{task_id} completed successfully",
    data={
        "id": task_id,
        "status": "completed",
        "progress": 100
    }
)
```

### 前端实时更新流程
1. 页面加载时初始化 WebSocket 连接
2. 订阅 `system` 主题
3. 接收到 `TASK_*` 事件时:
   - 更新本地缓存
   - 查找对应的表格行
   - 更新状态徽章 (带动画)
   - 更新进度条 (如果有)
   - 更新重试次数
   - 更新时间戳
4. 任务完成/失败时显示通知

## 技术细节

### 任务缓存机制
```javascript
let tasksCache = new Map(); // {task_id: task_data}

// 加载时更新缓存
res.data.items.forEach(task => tasksCache.set(task.id, task));

// 实时更新时更新缓存
tasksCache.set(taskId, taskData);
```

### DOM 查询优化
使用 `data-task-id` 属性快速定位行:
```javascript
const row = document.querySelector(`tr[data-task-id="${taskId}"]`);
```

### CSS 类命名规范
- `.task-status-badge`: 状态徽章
- `.task-progress-bar`: 进度条
- `.task-retry-count`: 重试次数单元格
- `.task-time`: 时间戳单元格

## 性能优化

1. **选择性更新**: 只更新变更的字段，不重新渲染整行
2. **动画节流**: 状态变更动画限制为 500ms
3. **缓存机制**: 减少 DOM 查询次数
4. **事件委托**: 使用 `data-task-id` 属性而非内联事件

## 测试验证

### 手动测试步骤
1. 打开任务队列页面
2. 观察右下角连接状态指示器 (应显示"实时连接")
3. 在后端触发任务状态变更
4. 观察前端表格实时更新 (状态徽章应有闪烁动画)
5. 检查浏览器控制台日志: `[Tasks] WebSocket connected`

### 自动化测试 (待实施)
- [ ] 编写 E2E 测试验证实时更新
- [ ] 测试 WebSocket 断线重连
- [ ] 测试降级到 API 轮询
- [ ] 测试进度条更新

## 已知限制

1. **进度百分比**: 需要后端在任务数据中提供 `progress` 字段
2. **日志流式输出**: 当前仅支持错误日志查看，实时日志流待 Phase 3.3 实现
3. **批量操作**: 暂不支持批量更新任务

## 下一步计划

### Phase 3.3: 日志实时流 (预计 3-4 小时)
- [ ] 在 `logs.html` 中集成 WebSocket
- [ ] 订阅 `logs` 主题
- [ ] 实现虚拟滚动 (处理大量日志行)
- [ ] 添加暂停/恢复流控制按钮
- [ ] 实现自动滚动到底部

### 后端增强 (可选)
- [ ] 在 TaskQueue 模型中添加 `progress` 字段
- [ ] 实现任务进度计算逻辑
- [ ] 添加任务日志流式 API

## 文档更新

- [x] 创建 Phase 3.2 进度追踪文档
- [ ] 更新 `Frontend_Backend_Integration_Plan.md`
- [ ] 更新用户使用指南

---

**状态**: ✅ **Phase 3.2 已完成 (前端部分)**  
**待完善**: 后端任务进度计算、日志流式输出  
**下一阶段**: Phase 3.3 - 日志实时流  
**负责人**: AI Agent (Antigravity)  
**完成时间**: 2026-01-15 22:10
