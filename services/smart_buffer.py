import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Callable, Awaitable
from core.config import settings

logger = logging.getLogger(__name__)

class SmartBufferService:
    """
    智能聚合缓冲区 (公交车机制)
    解决连珠炮发图和短时间内多条消息刷屏问题
    """
    
    def __init__(self):
        # 存储机制: (rule_id, target_chat_id) -> { "messages": [], "timer": Task, "last_received": float, "config": dict }
        self._buffers: Dict[tuple, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def push(self, rule_id: int, target_chat_id: int, context: Any, send_callback: Callable[[List[Any]], Awaitable[None]], **kwargs):
        """
        将消息推入缓冲区
        :param kwargs: 可选参数，覆盖全局设置，如 debounce_time, max_wait_time
        """
        key = (rule_id, target_chat_id)
        
        # 实时从 settings 获取最新全局配置，确保热更新生效
        # 如果 kwargs 传入了，则以 kwargs 为准（实现按规则自定义）
        config = {
            "enabled": kwargs.get('enabled') if kwargs.get('enabled') is not None else getattr(settings, 'ENABLE_SMART_BUFFER', True),
            "debounce": kwargs.get('debounce_time') or getattr(settings, 'SMART_BUFFER_DEBOUNCE', 3.5),
            "max_wait": kwargs.get('max_wait_time') or getattr(settings, 'SMART_BUFFER_MAX_WAIT', 8.0),
            "max_batch": kwargs.get('max_batch_size') or getattr(settings, 'SMART_BUFFER_MAX_BATCH', 10)
        }

        if not config["enabled"]:
            await send_callback([context])
            return

        async with self._lock:
            if key not in self._buffers:
                self._buffers[key] = {
                    "contexts": [context],
                    "timer": None,
                    "start_time": time.time(),
                    "last_received": time.time(),
                    "config": config
                }
                # 启动发车计时器
                self._buffers[key]["timer"] = asyncio.create_task(
                    self._wait_and_flush(key, send_callback)
                )
                logger.debug(f"🚍 [小车启动] 规则 {rule_id} -> 目标 {target_chat_id} 开始收集消息 (防抖: {config['debounce']}s)")
            else:
                buffer = self._buffers[key]
                buffer["contexts"].append(context)
                buffer["last_received"] = time.time()
                # 更新配置（以防规则在运行中被修改）
                buffer["config"].update(config)
                
                # 如果达到最大批次（如10张图），立即触发发车
                if len(buffer["contexts"]) >= buffer["config"]["max_batch"]:
                    logger.info(f"🚀 [满载发车] 规则 {rule_id} 积压达 {len(buffer['contexts'])} 条，立即发出")
                    if buffer["timer"]:
                        buffer["timer"].cancel()
                    await self._flush(key, send_callback)

    async def _wait_and_flush(self, key: tuple, send_callback: Callable):
        """计时器逻辑"""
        try:
            while True:
                buffer = self._buffers.get(key)
                if not buffer:
                    break
                    
                now = time.time()
                elapsed_since_last = now - buffer["last_received"]
                total_wait = now - buffer["start_time"]
                
                config = buffer["config"]
                
                # 条件 1: 防抖超时
                # 条件 2: 强行发车超时
                if elapsed_since_last >= config["debounce"] or total_wait >= config["max_wait"]:
                    reason = "防抖超时" if elapsed_since_last >= config["debounce"] else "强行发车"
                    logger.info(f"🚏 [站点发车] 规则 {key[0]} {reason}，发送 {len(buffer['contexts'])} 条消息 (已等 {round(total_wait, 1)}s)")
                    await self._flush(key, send_callback)
                    break
                
                # 每隔 0.1 秒检查一次
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"缓冲区计时器异常: {e}")
            async with self._lock:
                self._buffers.pop(key, None)

    async def _flush(self, key: tuple, send_callback: Callable):
        """执行发送并清理缓冲区"""
        async with self._lock:
            buffer = self._buffers.pop(key, None)
            if not buffer or not buffer["contexts"]:
                return
            
            contexts = buffer["contexts"]
            
        # 在锁外执行回调，避免阻塞新消息推入
        try:
            await send_callback(contexts)
        except Exception as e:
            logger.error(f"缓冲区发送回调失败: {e}")

# 全局单例
smart_buffer = SmartBufferService()
