import asyncio
import logging
from collections import defaultdict
from typing import Callable, Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EventBus:
    """
    增强型事件总线
    
    功能:
    1. 事件订阅/发布
    2. 通配符订阅 ("*" 匹配所有事件)
    3. 日志钩子 (可选记录所有事件)
    4. 事件统计
    5. WebSocket 广播集成
    
    Phase G.1: 全局事件日志增强
    """
    
    # 需要记录日志的事件前缀
    LOG_EVENT_PREFIXES = ("FORWARD_", "ERROR_", "SYSTEM_", "AUTH_", "RULE_")
    
    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._wildcard_listeners: List[Callable] = []  # 通配符监听器
        self._log_enabled = True  # 是否启用事件日志
        self._broadcast_enabled = True  # 是否启用 WebSocket 广播
        self._stats: Dict[str, int] = defaultdict(int)  # 事件计数统计
        self._last_event_time: Dict[str, datetime] = {}  # 最后事件时间
        self._broadcaster: Optional[Callable] = None  # WebSocket 广播器回调
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型，使用 "*" 订阅所有事件
            handler: 处理函数 (同步或异步)
        """
        if event_type == "*":
            self._wildcard_listeners.append(handler)
            logger.debug(f"Wildcard listener registered: {handler.__name__}")
        else:
            self._listeners[event_type].append(handler)
            logger.debug(f"Event listener registered: {event_type} -> {handler.__name__}")
    
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅"""
        if event_type == "*":
            if handler in self._wildcard_listeners:
                self._wildcard_listeners.remove(handler)
        else:
            if handler in self._listeners[event_type]:
                self._listeners[event_type].remove(handler)

    async def publish(self, event_type: str, data: Any = None, wait: bool = False) -> None:
        """
        发布事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
            wait: 是否等待所有处理器完成
        """
        # 更新统计
        self._stats[event_type] += 1
        self._last_event_time[event_type] = datetime.utcnow()
        
        # 日志钩子
        if self._log_enabled and self._should_log(event_type):
            self._log_event(event_type, data)
        
        # WebSocket 广播钩子
        if self._broadcast_enabled:
            asyncio.create_task(self._broadcast_event(event_type, data))
        
        # 获取所有监听器
        handlers = self._listeners.get(event_type, []) + self._wildcard_listeners
        
        if not handlers:
            return
        
        if wait:
            # 关键路径：等待执行结果，抛出异常以便上层捕获处理
            for handler in handlers:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
        else:
            # Fire-and-forget: 不阻塞主线程
            for handler in handlers:
                asyncio.create_task(self._safe_execute(handler, event_type, data))

    async def _safe_execute(self, handler: Callable, event_type: str, data: Any) -> None:
        """安全执行处理器"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(data)
            else:
                handler(data)
        except Exception as e:
            logger.error(f"Event handler error [{handler.__name__}] for {event_type}: {e}")
            # 使用全局异常处理器记录
            try:
                from services.exception_handler import exception_handler
                await exception_handler.handle_exception(
                    e,
                    context={"event_type": event_type, "handler": handler.__name__},
                    task_name=f"EventHandler:{handler.__name__}"
                )
            except Exception:
                pass  # 防止循环错误
    
    def _should_log(self, event_type: str) -> bool:
        """判断是否需要记录日志"""
        return any(event_type.startswith(prefix) for prefix in self.LOG_EVENT_PREFIXES)
    
    def _log_event(self, event_type: str, data: Any) -> None:
        """记录事件日志"""
        # 根据事件类型选择日志级别
        if event_type.startswith("ERROR_"):
            logger.warning(f"📢 Event: {event_type}")
        else:
            logger.debug(f"📢 Event: {event_type}")
    
    async def _broadcast_event(self, event_type: str, data: Any) -> None:
        """广播事件到 WebSocket"""
        if self._broadcaster is not None:
            try:
                if asyncio.iscoroutinefunction(self._broadcaster):
                    await self._broadcaster(event_type, data)
                else:
                    self._broadcaster(event_type, data)
            except Exception as e:
                logger.debug(f"Event broadcast failed: {e}")

    async def emit(self, event_type: str, data: Any = None, wait: bool = False) -> None:
        """
        发布事件 (publish 的别名，用于兼容旧版调用)
        """
        await self.publish(event_type, data, wait=wait)

    def set_broadcaster(self, broadcaster: Callable) -> None:
        """设置广播器的回调"""
        self._broadcaster = broadcaster
    
    def set_log_enabled(self, enabled: bool) -> None:
        """启用/禁用事件日志"""
        self._log_enabled = enabled
    
    def set_broadcast_enabled(self, enabled: bool) -> None:
        """启用/禁用 WebSocket 广播"""
        self._broadcast_enabled = enabled
    
    def get_stats(self) -> Dict:
        """获取事件统计"""
        return {
            "event_counts": dict(self._stats),
            "total_events": sum(self._stats.values()),
            "unique_event_types": len(self._stats),
            "listener_counts": {
                event: len(handlers) for event, handlers in self._listeners.items()
            },
            "wildcard_listeners": len(self._wildcard_listeners),
            "last_events": {
                event: time.isoformat() for event, time in self._last_event_time.items()
            }
        }
    
    def clear_stats(self) -> None:
        """清除统计数据"""
        self._stats.clear()
        self._last_event_time.clear()