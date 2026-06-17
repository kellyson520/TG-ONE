"""
统一消息监听器

整合原有两个版本的优点，使用端口/适配器模式分离框架事件和业务处理。
提供清晰的监听器设置接口。
"""

from __future__ import annotations
import logging
import asyncio
import time
from typing import Any

from telethon import events

from core.container import container
from core.helpers.sleep_manager import sleep_manager
from core.config import settings

# 获取logger
logger = logging.getLogger(__name__)


class LogLimiter:
    """日志频率限制器，防止在循环或高频事件中刷屏"""
    def __init__(self, interval: int = 60):
        self.interval = interval
        self._last_times = {}

    def should_log(self, key: str) -> bool:
        now = time.time()
        if key not in self._last_times or (now - self._last_times[key]) >= self.interval:
            self._last_times[key] = now
            return True
        return False


# 实例化限制器 (60秒内同类错误只报一次)
error_limiter = LogLimiter(60)


async def _resolve_bot_id(bot_client):
    """获取机器人ID，用于过滤机器人消息"""
    try:
        me = await bot_client.get_me()
        bot_id = me.id
        logger.info(f"机器人监听器设置完成，ID: {bot_id}")
        return bot_id
    except Exception as e:
        logger.error(f"获取机器人ID时出错: {str(e)}")
        if settings.BOT_TOKEN:
            try:
                bot_id = int(settings.BOT_TOKEN.split(":")[0])
                logger.info(f"从Token降级解析机器人ID: {bot_id}")
                return bot_id
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
    return None


def _create_should_process_filter(bot_id):
    """创建消息过滤函数：区分命令和普通消息"""
    def should_process(event):
        if bot_id and event.sender_id == bot_id:
            return False
        msg_text = event.message.text or ""
        if "❌" in msg_text and ("ERROR" in msg_text or "CRITICAL" in msg_text):
            if " | " in msg_text:
                return False
        if event.out:
            message_text = event.message.text or ""
            if message_text.strip().startswith('/'):
                return False
            return True
        return True
    return should_process


def _setup_priority_cache():
    """初始化优先级缓存状态和事件订阅"""
    _priority_state = {"map": {}, "last_update": 0}

    def _handle_rule_update(data=None):
        logger.info("🔄 [监听器] 检测到规则变更，将刷新优先级缓存")
        _priority_state["last_update"] = 0

    container.bus.subscribe("RULE_UPDATED", _handle_rule_update)

    async def _get_chat_priority(chat_id: int) -> int:
        now = time.time()
        if now - _priority_state["last_update"] > 15:
            try:
                _priority_state["map"] = await container.rule_repo.get_priority_map()
                _priority_state["last_update"] = now
                logger.debug(f"Priority map updated: {len(_priority_state['map'])} entries")
            except Exception as e:
                logger.warning(f"Priority map update failed: {e}")
        return _priority_state["map"].get(chat_id, 0)

    return _get_chat_priority


async def _handle_download_mode(event, user_session):
    """处理下载模式下的消息，返回True表示已拦截"""
    logger.info(f"[监听器] 检测到下载模式: 发送者ID={event.sender_id}, 聊天ID={event.chat_id}")
    if event.message.media:
        payload = {
            "chat_id": event.chat_id,
            "message_id": event.id,
            "manual_trigger": True,
            "target_chat_id": user_session.get(event.chat_id, {}).get('target_chat_id')
        }
        await container.queue_service.enqueue(("manual_download", payload, 100))
        await event.respond("✅ 已加入下载队列。")
        if event.chat_id in user_session:
            user_session.pop(event.chat_id)
        from core.helpers.id_utils import get_display_name_async
        from core.helpers.priority_utils import format_priority_log
        chat_display = await get_display_name_async(event.chat_id)
        p_desc = format_priority_log(100, event.chat_id)
        logger.info(f"🚀 [监听器] 手动下载任务已写入队列: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 优先级={p_desc}")
    else:
        if event.text != "/cancel":
            await event.respond("⚠️ 请发送文件。")
            logger.debug(f"[监听器] 下载模式下收到非文件消息: 发送者ID={event.sender_id}, 聊天ID={event.chat_id}, 内容={event.text[:50]}...")
        else:
            logger.info(f"[监听器] 用户取消下载模式: 发送者ID={event.sender_id}, 聊天ID={event.chat_id}")
            if event.chat_id in user_session:
                user_session.pop(event.chat_id)
            await event.respond("❌ 下载已取消。")
    return True


async def _preprocess_event(event):
    """预处理事件：记录活动、日志、预加载发送者、热词采集"""
    sleep_manager.record_activity()
    from core.helpers.id_utils import get_display_name_async
    chat_display = await get_display_name_async(event.chat_id)
    logger.info(f"📥 [监听器] 收到新消息: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 发送者ID={event.sender_id}, 媒体={bool(event.message.media)}")

    if event.sender_id:
        try:
            from services.network.api_optimization import get_api_optimizer
            api_optimizer = get_api_optimizer()
            if api_optimizer:
                asyncio.create_task(api_optimizer.get_users_batch([event.sender_id]))
        except Exception as e:
            if error_limiter.should_log("sender_preload"):
                logger.error(f"预加载发送者信息失败: {e}", exc_info=True)

    if getattr(settings, "ENABLE_HOTWORD", True) and getattr(event, "message", None):
        msg_text = getattr(event, "raw_text", getattr(event.message, "message", ""))
        if msg_text:
            try:
                if hasattr(container, "hotword_service"):
                    channel_name = chat_display.replace("/", "_").replace("\\", "_")
                    from middlewares.hotword import get_hotword_collector
                    get_hotword_collector().queue.put_nowait((channel_name, event.sender_id, msg_text))
            except asyncio.QueueFull:
                if error_limiter.should_log("hotword_queue_full"):
                    logger.warning("热词采集队列已满，已丢弃当前消息以保护主监听流程")
            except Exception as e:
                if error_limiter.should_log("hotword_extract"):
                    logger.error(f"❌ [监听器] 直接提取热词失败: {e}", exc_info=True)

    return chat_display


async def _enqueue_normal_message(event, get_chat_priority):
    """计算优先级并写入普通消息队列"""
    payload = {
        "chat_id": event.chat_id,
        "message_id": event.id,
        "has_media": bool(event.message.media),
        "grouped_id": event.message.grouped_id
    }
    base_priority = 10
    if event.message.date:
        try:
            msg_ts = event.message.date.timestamp()
            if time.time() - msg_ts > 300:
                base_priority = 0
        except Exception as e:
            logger.debug(
                "[监听器] 无法解析消息时间戳: 聊天ID=%s, 消息ID=%s, 错误=%s",
                event.chat_id, event.id, e, exc_info=True,
            )
    rule_priority = await get_chat_priority(event.chat_id)
    final_priority = base_priority + rule_priority
    await container.queue_service.enqueue(("process_message", payload, final_priority))
    from core.helpers.id_utils import get_display_name_async
    from core.helpers.priority_utils import format_priority_log
    chat_display = await get_display_name_async(event.chat_id)
    p_desc = format_priority_log(final_priority, event.chat_id)
    logger.info(f"✅ [监听器] 普通消息已写入队列: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 优先级={p_desc}, 分组ID={event.message.grouped_id}")


async def setup_listeners(user_client: Any, bot_client: Any) -> None:
    """
    设置统一的消息监听器
    
    遵循 Dumb Listener 原则：
    - 只负责接收事件并写入任务队列
    - 不做任何业务判断或处理
    - 保持极致的轻量和快速
    
    Args:
        user_client: 用户客户端（用于监听消息和转发）
        bot_client: 机器人客户端（用于处理命令和转发）
    """
    logger.info("开始设置统一消息监听器")

    bot_id = await _resolve_bot_id(bot_client)
    should_process = _create_should_process_filter(bot_id)
    get_chat_priority = _setup_priority_cache()

    @user_client.on(events.NewMessage(func=should_process))
    async def user_message_listener(event):
        """用户消息监听器 - 只写入任务队列"""
        try:
            await _preprocess_event(event)

            from services.session_service import session_manager
            user_session = session_manager.user_sessions.get(event.sender_id, {})
            state = user_session.get(event.chat_id, {}).get('state')
            logger.debug(f"[监听器] 检查会话状态: 发送者ID={event.sender_id}, 聊天ID={event.chat_id}, 状态={state}")

            if state == "waiting_for_file":
                await _handle_download_mode(event, user_session)
                return

            await _enqueue_normal_message(event, get_chat_priority)
        except Exception as e:
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.error(f"❌ [监听器] 消息处理失败: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 错误={str(e)}", exc_info=True)

    @bot_client.on(events.NewMessage)
    async def bot_message_listener(event):
        """机器人消息监听器 - 只处理命令"""
        try:
            sleep_manager.record_activity()
            if event.out or event.sender_id == bot_id:
                return
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.info(f"🤖 [Bot监听器] 收到Bot命令: 来源={chat_display}({event.chat_id}), 发送者ID={event.sender_id}, 命令={event.text}")
            from handlers import bot_handler
            await bot_handler.handle_command(bot_client, event)
            logger.info(f"✅ [Bot监听器] Bot命令处理完成: 来源={chat_display}({event.chat_id}), 命令={event.text}")
        except Exception as e:
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.error(f"❌ [Bot监听器] Bot命令处理失败: 来源={chat_display}({event.chat_id}), 命令={event.text}, 错误={str(e)}", exc_info=True)

    from handlers import bot_handler as bot_handler_module
    bot_client.add_event_handler(bot_handler_module.callback_handler)

    logger.info("统一消息监听器设置完成")
    logger.info("- 用户消息监听器：处理转发规则")
    logger.info("- 机器人消息监听器：处理命令和设置")
    logger.info("- 回调处理器：处理内联按钮回调")
