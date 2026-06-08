# API 性能优化技术方案 (API Optimization Spec)

## 1. 现状痛点
1. **惊群效应 (Thundering Herd)**: 高并发下同一个 `chat_id` 的统计信息在缓存失效时会被并发调用多次。
2. **长阻塞 (Blocking)**: `client.get_entity` 在网络不佳时会长时间挂起，没有超时机制。
3. **资源枯竭**: 过多的并发 API 请求可能导致数据库连接池或协程阻塞。

## 2. 技术方案

### 2.1 请求合并 (Request Coalescing)
在 `MultiLevelCache` 或 `cached` 装饰器中引入一个异步锁字典：
```python
_request_locks: Dict[str, asyncio.Lock] = {}

async def cached_call(key):
    if key in cache: return cache[key]
    
    # 获取或创建该键的锁
    lock = _request_locks.setdefault(key, asyncio.Lock())
    async with lock:
        # 双重检查命中
        if key in cache: return cache[key]
        result = await func()
        cache[key] = result
        return result
    finally:
        # 可选：清理锁（需注意并发安全）
        pass
```

### 2.2 全局并发限制 (Semaphore)
在 `TelegramAPIOptimizer` 初始化时创建信号量：
```python
self._api_semaphore = asyncio.Semaphore(10)

async def call_api(self):
    async with self._api_semaphore:
        return await self.client(...)
```

### 2.3 超时矩阵 (Timeout Matrix)
| 操作类型 | 指标 | 建议超时 |
| :--- | :--- | :--- |
| `get_entity` | P99 需低于 | 5.0s |
| `GetFullChannelRequest` | 核心调用 | 8.0s |
| `GetUsersRequest` | 批量调用 | 10.0s |

## 3. 日志规范变更
*   `缓存命中` (Hit): `INFO` -> `DEBUG`
*   `性能警告` (Warning): 阈值保持 5.0s
*   `API 失败` (Error): 增强错误元数据，包含请求 ID 和队列深度
