# 修复异步调用和空值检查错误

## 任务概述
修复两个运行时错误：
1. RuntimeWarning: coroutine 'EventBus.publish' was never awaited
2. TypeError: None is not a callable object

## 错误详情

### 错误 1: 协程未被 await
**文件**: `services/update_service.py`
**位置**: 第 48 行及多处

**错误信息**:
```
RuntimeWarning: coroutine 'EventBus.publish' was never awaited
  self._bus.publish(name, data)
```

**根本原因**:
- `EventBus.publish()` 是异步方法 (async def)
- `_emit_event()` 方法是同步的，直接调用了异步方法但没有 await
- 导致协程对象被创建但从未执行

### 错误 2: None 不是可调用对象
**文件**: `handlers/button/callback/callback_handlers.py`
**位置**: 第 348 行

**错误信息**:
```
TypeError: None is not a callable object
  sig = inspect.signature(handler)
```

**根本原因**:
- `callback_router.match(data)` 返回 `(handler, params)`
- 某些情况下 `handler` 可能为 `None`
- 代码未检查就直接调用 `inspect.signature(handler)`

## 修复方案

### 修复 1: update_service.py

#### 1. 将 `_emit_event` 改为异步方法
**修改前**:
```python
def _emit_event(self, name: str, data: dict):
    """触发系统事件"""
    if self._bus:
        self._bus.publish(name, data)
```

**修改后**:
```python
async def _emit_event(self, name: str, data: dict):
    """触发系统事件"""
    if self._bus:
        await self._bus.publish(name, data)
```

#### 2. 所有调用处添加 await (9处)
- 第 125 行: `trigger_update()`
- 第 174 行: `post_update_bootstrap()`
- 第 180 行: `post_update_bootstrap()`
- 第 186 行: `post_update_bootstrap()`
- 第 260 行: `verify_update_health()`
- 第 268 行: `verify_update_health()`
- 第 286 行: `verify_update_health()`
- 第 305 行: `_stabilize_after_delay()`

### 修复 2: callback_handlers.py

**修改位置**: 第 343-344 行之间

**修改前**:
```python
handler, params = match_result
event.router_params = params
```

**修改后**:
```python
handler, params = match_result

# [Fix] 检查 handler 是否为 None
if handler is None:
    logger.warning(f"路由匹配成功但处理器为空: {data}")
    await event.answer("操作已过期或指令无效", alert=True)
    return

event.router_params = params
```

## 影响范围
- ✅ UpdateService 所有事件发布
- ✅ 回调处理器的空值安全性
- ✅ 系统更新流程的事件通知
- ✅ 用户回调操作的错误提示

## 验证方法
```bash
# 检查是否还有未 await 的协程
python -m pylint services/update_service.py --disable=all --enable=W1514

# 测试回调处理
python -c "from handlers.button.callback.callback_handlers import handle_callback; print('✅ 导入成功')"
```

## 状态
- [x] 修复 update_service.py 异步调用
- [x] 修复 callback_handlers.py 空值检查
- [ ] 运行集成测试
- [ ] 部署验证
