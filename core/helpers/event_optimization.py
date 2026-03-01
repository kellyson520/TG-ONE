"""
事件驱动监控优化
使用官方事件API替代轮询机制，提升响应速度和降低资源消耗
"""

from datetime import datetime

import asyncio
import logging
import time
from telethon import TelegramClient, events
from typing import Any, Callable, Dict, List, Set

logger = logging.getLogger(__name__)


class EventOptimizer:
    """事件驱动优化器"""

    def __init__(self) -> None:
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.event_stats: Dict[str, Any] = {
            "messages_processed": 0,
            "events_handled": 0,
            "errors_count": 0,
            "last_reset": datetime.now(),
        }
        self.rate_limiter = RateLimiter()

    async def setup_optimized_listeners(
        self, user_client: TelegramClient, bot_client: TelegramClient
    ) -> None:
        """
        设置优化的事件监听器
        使用事件驱动替代轮询，提升性能
        """
        logger.info("设置优化的事件监听器...")

        # 2. 消息编辑事件 - 实时处理消息更新
        @user_client.on(events.MessageEdited)
        async def optimized_edit_handler(event: events.MessageEdited.Event) -> None:
            """优化的消息编辑处理器"""
            try:
                logger.debug(f"消息编辑事件: {event.chat_id}")
                self.event_stats["events_handled"] += 1

                # 可以在这里添加消息编辑的处理逻辑
                # 例如：更新转发的消息、重新评估关键字匹配等

            except Exception as e:
                logger.error(f"处理消息编辑事件失败: {str(e)}")
                self.event_stats["errors_count"] += 1

        # 3. 消息删除事件 - 实时处理消息删除
        @user_client.on(events.MessageDeleted)
        async def optimized_delete_handler(event: events.MessageDeleted.Event) -> None:
            """优化的消息删除处理器"""
            try:
                logger.debug(f"消息删除事件: {len(event.deleted_ids)} 条消息")
                self.event_stats["events_handled"] += 1

                # 可以在这里添加消息删除的处理逻辑
                # 例如：清理相关的转发记录、更新统计等

            except Exception as e:
                logger.error(f"处理消息删除事件失败: {str(e)}")
                self.event_stats["errors_count"] += 1

        # 4. 聊天动作事件 - 实时监控用户活动
        @user_client.on(events.UserUpdate)
        async def optimized_user_update_handler(event: events.UserUpdate.Event) -> None:
            """优化的用户状态更新处理器"""
            try:
                logger.debug(
                    f"用户状态更新: {event.user_id if hasattr(event, 'user_id') else 'unknown'}"
                )
                self.event_stats["events_handled"] += 1

                # 实时更新用户信息缓存
                mod = __import__('services.batch_user_service', fromlist=['get_batch_user_service'])
                batch_service = mod.get_batch_user_service()

                if hasattr(event, "user_id") and event.user_id:
                    # 异步更新用户信息
                    asyncio.create_task(
                        batch_service.get_users_info([event.user_id], use_cache=False)
                    )

            except Exception as e:
                logger.error(f"处理用户状态更新失败: {str(e)}")
                self.event_stats["errors_count"] += 1

        # 5. 聊天更新事件 - 实时监控聊天变化
        @user_client.on(events.ChatAction)
        async def optimized_chat_action_handler(event: events.ChatAction.Event) -> None:
            """优化的聊天动作处理器"""
            try:
                logger.debug(f"聊天动作: {event.chat_id}")
                self.event_stats["events_handled"] += 1

                # 使用官方API实时更新聊天统计
                mod = __import__('services.network.api_optimization', fromlist=['get_api_optimizer'])
                api_optimizer = mod.get_api_optimizer()

                if api_optimizer and event.chat_id:
                    # 异步更新聊天统计
                    asyncio.create_task(
                        api_optimizer.get_chat_statistics(event.chat_id)
                    )

            except Exception as e:
                logger.error(f"处理聊天动作失败: {str(e)}")
                self.event_stats["errors_count"] += 1

        logger.info("优化的事件监听器设置完成")

    def get_event_stats(self) -> Dict[str, Any]:
        """获取事件处理统计"""
        now = datetime.now()
        runtime = (now - self.event_stats["last_reset"]).total_seconds()

        return {
            "messages_processed": self.event_stats["messages_processed"],
            "events_handled": self.event_stats["events_handled"],
            "errors_count": self.event_stats["errors_count"],
            "messages_per_second": self.event_stats["messages_processed"]
            / max(runtime, 1),
            "events_per_second": self.event_stats["events_handled"] / max(runtime, 1),
            "error_rate": float(self.event_stats["errors_count"])
            / max(
                int(self.event_stats["messages_processed"])
                + int(self.event_stats["events_handled"]),
                1,
            ),
            "runtime_seconds": runtime,
            "optimization_enabled": True,
        }

    def reset_stats(self) -> None:
        """重置统计"""
        self.event_stats = {
            "messages_processed": 0,
            "events_handled": 0,
            "errors_count": 0,
            "last_reset": datetime.now(),
        }
        logger.info("事件统计已重置")


class RateLimiter:
    """速率限制器"""

    def __init__(self, max_requests: int = 100, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: List[float] = []

    async def check_rate_limit(self) -> bool:
        """检查速率限制"""
        now = time.time()

        # 清理过期的请求记录
        self.requests = [
            req_time for req_time in self.requests if now - req_time < self.time_window
        ]

        # 检查是否超过限制
        if len(self.requests) >= self.max_requests:
            return False

        # 记录新请求
        self.requests.append(now)
        return True


class EventDrivenMonitor:
    """事件驱动监控器 - 替代轮询机制"""

    def __init__(self) -> None:
        self.monitoring_active = False
        self.monitor_tasks: Set[asyncio.Task] = set()

    async def start_monitoring(self, user_client: TelegramClient) -> None:
        """
        启动事件驱动监控
        替代传统的轮询机制，减少API调用和资源消耗
        """
        if self.monitoring_active:
            logger.warning("监控已在运行中")
            return

        logger.info("启动事件驱动监控...")
        self.monitoring_active = True

        # 定期统计任务（低频率）
        async def periodic_stats() -> None:
            while self.monitoring_active:
                try:
                    # 每10分钟收集一次统计
                    await asyncio.sleep(600)

                    # 使用官方API获取聊天统计
                    mod = __import__('services.network.api_optimization', fromlist=['get_api_optimizer'])
                    api_optimizer = mod.get_api_optimizer()

                    if api_optimizer:
                        # 获取活跃聊天列表（从数据库）
                        from models.models import Chat
                        from sqlalchemy import select
                        from core.container import container

                        async with container.db.get_session(readonly=True) as session:
                            stmt = select(Chat.telegram_chat_id).filter(Chat.is_active == True).limit(20)
                            result = await session.execute(stmt)
                            active_chats = result.all()

                            if active_chats:
                                chat_ids = [chat[0] for chat in active_chats if chat[0]]
                                # 批量更新统计（异步）
                                asyncio.create_task(
                                    api_optimizer.get_multiple_chat_statistics(chat_ids)
                                )
                                logger.info(f"定期统计更新: {len(chat_ids)} 个聊天")

                except Exception as e:
                    logger.error(f"定期统计任务失败: {str(e)}")

        # 启动监控任务
        task = asyncio.create_task(periodic_stats())
        self.monitor_tasks.add(task)

        logger.info("事件驱动监控启动完成")

    async def stop_monitoring(self) -> None:
        """停止监控"""
        logger.info("停止事件驱动监控...")
        self.monitoring_active = False

        # 取消所有监控任务
        for task in self.monitor_tasks:
            if not task.done():
                task.cancel()

        # 等待任务完成
        if self.monitor_tasks:
            await asyncio.gather(*self.monitor_tasks, return_exceptions=True)

        self.monitor_tasks.clear()
        logger.info("事件驱动监控已停止")


# 全局实例
event_optimizer = EventOptimizer()
event_monitor = EventDrivenMonitor()


def get_event_optimizer() -> EventOptimizer:
    """获取事件优化器实例"""
    return event_optimizer


def get_event_monitor() -> EventDrivenMonitor:
    """获取事件监控器实例"""
    return event_monitor
