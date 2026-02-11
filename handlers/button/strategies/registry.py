import logging
import time
from typing import Dict, Type, Optional, List
from collections import defaultdict
from datetime import datetime, timedelta
from .base import BaseMenuHandler

logger = logging.getLogger(__name__)

class MenuHandlerRegistry:
    """
    Registry for Menu Strategies.
    Implements the Strategy Pattern to dispatch actions to the correct handler.
    """
    _handlers: List[BaseMenuHandler] = []
    _initialized = False
    
    # Performance Monitoring
    _action_stats: Dict[str, Dict] = defaultdict(lambda: {
        "count": 0,
        "total_time": 0.0,
        "avg_time": 0.0,
        "max_time": 0.0,
        "last_execution": None
    })
    _unmatched_actions: Dict[str, int] = defaultdict(int)
    
    # High-frequency actions (will be logged with performance metrics)
    HIGH_FREQUENCY_ACTIONS = {
        "main_menu", "main_menu_refresh", "refresh_main_menu",
        "forward_hub", "refresh_forward_hub",
        "list_rules", "rule_detail",
        "toggle_rule", "toggle_setting"
    }

    @classmethod
    def register(cls, handler_cls: Type[BaseMenuHandler]):
        """
        Decorator to register a new handler strategy.
        """
        # We instantiate the handler immediately upon registration
        # In a more complex DI system, we might just store the class
        instance = handler_cls()
        cls._handlers.append(instance)
        logger.info(f"Registered Menu Strategy: {handler_cls.__name__}")
        return handler_cls

    @classmethod
    async def dispatch(cls, event, action: str, **kwargs):
        """
        Iterate through registered handlers and find the one that matches the action.
        Returns:
            bool: True if a handler was found and executed, False otherwise.
        """
        start_time = time.perf_counter()
        matched = False
        handler_name = None
        
        try:
            for handler in cls._handlers:
                try:
                    if await handler.match(action, **kwargs):
                        handler_name = handler.__class__.__name__
                        logger.debug(f"Action '{action}' matched by {handler_name}")
                        
                        # Execute handler
                        await handler.handle(event, action, **kwargs)
                        matched = True
                        break
                except Exception as e:
                    logger.error(
                        f"Error in {handler.__class__.__name__} handling action '{action}': {e}",
                        exc_info=True,
                        extra={
                            "action": action,
                            "handler": handler.__class__.__name__,
                            "user_id": getattr(event, "sender_id", None),
                            "chat_id": getattr(event, "chat_id", None)
                        }
                    )
                    continue
            
            # Log if no handler found
            if not matched:
                cls._log_unmatched_action(action, event)
                logger.warning(
                    f"No handler found for action: {action}",
                    extra={
                        "action": action,
                        "user_id": getattr(event, "sender_id", None),
                        "chat_id": getattr(event, "chat_id", None),
                        "total_unmatched_count": cls._unmatched_actions[action]
                    }
                )
                return False
            
            return True
            
        finally:
            # Performance monitoring
            execution_time = time.perf_counter() - start_time
            
            if matched:
                cls._record_performance(action, execution_time, handler_name)
                
                # Log high-frequency actions with performance metrics
                if action in cls.HIGH_FREQUENCY_ACTIONS:
                    stats = cls._action_stats[action]
                    logger.info(
                        f"[PERF] {action} executed in {execution_time*1000:.2f}ms "
                        f"(avg: {stats['avg_time']*1000:.2f}ms, count: {stats['count']})",
                        extra={
                            "action": action,
                            "handler": handler_name,
                            "execution_time_ms": round(execution_time * 1000, 2),
                            "is_high_frequency": True
                        }
                    )
                
                # Warn if any action takes too long
                if execution_time > 1.0:  # 超过1秒
                    logger.warning(
                        f"[SLOW] Action '{action}' took {execution_time:.2f}s to complete",
                        extra={
                            "action": action,
                            "handler": handler_name,
                            "execution_time_s": round(execution_time, 2),
                            "threshold_s": 1.0
                        }
                    )

    @classmethod
    def _record_performance(cls, action: str, execution_time: float, handler_name: str):
        """记录action性能统计"""
        stats = cls._action_stats[action]
        stats["count"] += 1
        stats["total_time"] += execution_time
        stats["avg_time"] = stats["total_time"] / stats["count"]
        stats["max_time"] = max(stats["max_time"], execution_time)
        stats["last_execution"] = datetime.now()
        stats["handler"] = handler_name

    @classmethod
    def _log_unmatched_action(cls, action: str, event):
        """记录未匹配的action以便追踪"""
        cls._unmatched_actions[action] += 1
        
        # 如果同一个action频繁未匹配，发出告警
        count = cls._unmatched_actions[action]
        if count in [1, 5, 10, 50, 100]:  # 特定阈值时告警
            logger.error(
                f"[UNMATCHED] Action '{action}' has been unmatched {count} times",
                extra={
                    "action": action,
                    "unmatched_count": count,
                    "user_id": getattr(event, "sender_id", None),
                    "chat_id": getattr(event, "chat_id", None),
                    "is_critical": count >= 10
                }
            )

    @classmethod
    def get_registered_handlers(cls):
        return [h.__class__.__name__ for h in cls._handlers]
    
    @classmethod
    def get_performance_stats(cls, top_n: int = 10):
        """获取性能统计信息"""
        sorted_stats = sorted(
            cls._action_stats.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        return dict(sorted_stats[:top_n])
    
    @classmethod
    def get_unmatched_actions(cls):
        """获取未匹配actions的统计"""
        return dict(cls._unmatched_actions)
    
    @classmethod
    def reset_stats(cls):
        """重置统计数据（用于测试或周期性重置）"""
        cls._action_stats.clear()
        cls._unmatched_actions.clear()
