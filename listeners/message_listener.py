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
    
    # 获取机器人ID，用于过滤机器人消息
    bot_id = None
    try:
        me = await bot_client.get_me()
        bot_id = me.id
        logger.info(f"机器人监听器设置完成，ID: {bot_id}")
    except Exception as e:
        logger.error(f"获取机器人ID时出错: {str(e)}")
        # 尝试从 Token 解析 (Fallback)
        if settings.BOT_TOKEN:
            try:
                bot_id = int(settings.BOT_TOKEN.split(":")[0])
                logger.info(f"从Token降级解析机器人ID: {bot_id}")
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
    
    # 优化的消息过滤函数：区分命令和普通消息
    def should_process(event):
        # 不处理机器人自己发送的消息
        if bot_id and event.sender_id == bot_id:
            return False

        # 强制过滤系统日志消息 (防止死循环: Log Push -> Bot Receives -> Worker Error -> Log Push)
        # 特征: 包含 ❌ 和 "ERROR" 且来源可能不明
        msg_text = event.message.text or ""
        if "❌" in msg_text and ("ERROR" in msg_text or "CRITICAL" in msg_text):
            # 进一步检查是否符合日志格式 (e.g. "| core.")
            if " | " in msg_text:
                return False
        
        # 如果是自己发送的消息 (Outgoing)
        if event.out:
            # 检查是否为命令（以 / 开头）
            message_text = event.message.text or ""
            if message_text.strip().startswith('/'):
                # 自己发送的命令不处理（避免循环）
                return False
            # 自己发送的普通消息允许处理（支持自转发测试）
            return True
        
        # 其他人发送的消息都处理
        return True
    
    # Priority State (Closure)
    _priority_state = {
        "map": {},
        "last_update": 0
    }

    # [QoS Enhancement] 注册规则更新事件，实现秒级优先级同步
    def _handle_rule_update(data=None):
        logger.info("🔄 [监听器] 检测到规则变更，将刷新优先级缓存")
        _priority_state["last_update"] = 0
    
    container.bus.subscribe("RULE_UPDATED", _handle_rule_update)

    async def _get_chat_priority(chat_id: int) -> int:
        """获取聊天优先级 (带缓存)"""
        now = time.time()
        # Update cache every 15s (Reduce from 60s for better responsiveness)
        if now - _priority_state["last_update"] > 15:
            try:
                # Use lazy property to avoid import cycle issues if any
                _priority_state["map"] = await container.rule_repo.get_priority_map()
                _priority_state["last_update"] = now
                logger.debug(f"Priority map updated: {len(_priority_state['map'])} entries")
            except Exception as e:
                logger.warning(f"Priority map update failed: {e}")
        
        return _priority_state["map"].get(chat_id, 0)

    # 用户客户端监听器 - 只写入任务队列
    @user_client.on(events.NewMessage(func=should_process))
    async def user_message_listener(event):
        """用户消息监听器 - 只写入任务队列"""
        try:
            sleep_manager.record_activity()
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.info(f"📥 [监听器] 收到新消息: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 发送者ID={event.sender_id}, 媒体={bool(event.message.media)}")
            
            # [Optimization] 预加载发送者信息及缓存
            if event.sender_id:
                try:
                    from services.network.api_optimization import get_api_optimizer
                    api_optimizer = get_api_optimizer()
                    if api_optimizer:
                         # 预热用户缓存 (使用异步任务，不阻塞主监听流程)
                         asyncio.create_task(api_optimizer.get_users_batch([event.sender_id]))
                except Exception as e:
                    if error_limiter.should_log("sender_preload"):
                        logger.error(f"预加载发送者信息失败: {e}", exc_info=True)
            
            # [Hotword Auto-Collection]
            if getattr(settings, "ENABLE_HOTWORD", True) and getattr(event, "message", None):
                msg_text = getattr(event, "raw_text", getattr(event.message, "message", ""))
                if msg_text:
                    # 直接丢给热词层处理，这是最高效的方式
                    try:
                        from core.container import container
                        if hasattr(container, "hotword_service"):
                            channel_name = chat_display.replace("/", "_").replace("\\", "_")
                            from middlewares.hotword import get_hotword_collector
                            get_hotword_collector().queue.put_nowait((channel_name, event.sender_id, msg_text))
                    except Exception as e:
                        if error_limiter.should_log("hotword_extract"):
                            logger.error(f"❌ [监听器] 直接提取热词失败: {e}", exc_info=True)
            
            # 检查用户状态：是否处于下载模式？
            # 使用 session_service 替代已废弃的 state_manager
            from services.session_service import session_manager
            
            # 检查当前会话状态
            user_session = session_manager.user_sessions.get(event.sender_id, {})
            state = user_session.get(event.chat_id, {}).get('state')
            logger.debug(f"[监听器] 检查会话状态: 发送者ID={event.sender_id}, 聊天ID={event.chat_id}, 状态={state}")
            
            if state == "waiting_for_file":
                # 处于下载模式
                logger.info(f"[监听器] 检测到下载模式: 发送者ID={event.sender_id}, 聊天ID={event.chat_id}")
                if event.message.media:
                    # 分支 A: 手动下载任务
                    payload = {
                        "chat_id": event.chat_id,
                        "message_id": event.id,
                        "manual_trigger": True, # 标记为手动触发
                        "target_chat_id": user_session.get(event.chat_id, {}).get('target_chat_id') # 捕获目标聊天ID
                    }
                    # 写入高优先级任务 (Priority=100) -> 写入背压队列
                    await container.queue_service.enqueue(
                        ("manual_download", payload, 100)
                    )
                    
                    await event.respond("✅ 已加入下载队列。")
                    # 清除状态
                    if event.chat_id in user_session:
                        user_session.pop(event.chat_id)
                    from core.helpers.id_utils import get_display_name_async
                    from core.helpers.priority_utils import format_priority_log
                    chat_display = await get_display_name_async(event.chat_id)
                    p_desc = format_priority_log(100, event.chat_id)
                    logger.info(f"🚀 [监听器] 手动下载任务已写入队列: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 优先级={p_desc}")
                else:
                    # 如果发的不是文件（且不是取消指令）
                    if event.text != "/cancel":
                        await event.respond("⚠️ 请发送文件。")
                        logger.debug(f"[监听器] 下载模式下收到非文件消息: 发送者ID={event.sender_id}, 聊天ID={event.chat_id}, 内容={event.text[:50]}...")
                    else:
                        logger.info(f"[监听器] 用户取消下载模式: 发送者ID={event.sender_id}, 聊天ID={event.chat_id}")
                        if event.chat_id in user_session:
                            user_session.pop(event.chat_id)
                        await event.respond("❌ 下载已取消。")
                return  # 拦截结束，不走普通转发流程
            
            # 分支 B: 普通转发任务 (原有逻辑)
            # 仅当不是自己的消息且不在特殊状态时
            payload = {
                "chat_id": event.chat_id,
                "message_id": event.id,
                "has_media": bool(event.message.media),
                "grouped_id": event.message.grouped_id  # 捕获 grouped_id
            }
            
            # [Priority Enhancement] 计算优先级
            base_priority = 10 # 默认 Live 消息
            
            # 1. Catch-up Detection (Old Messages > 5 min -> Low Priority)
            if event.message.date:
                try:
                    msg_ts = event.message.date.timestamp()
                    if time.time() - msg_ts > 300: # 5 minutes
                        base_priority = 0
                except:
                    pass
            
            # 2. Rule based Priority
            rule_priority = await _get_chat_priority(event.chat_id)
            final_priority = base_priority + rule_priority
            
            # 写入背压消息队列 (由 MessageQueueService QoS 4.0 自动分流和处理背压)
            await container.queue_service.enqueue(
                ("process_message", payload, final_priority)
            )
            from core.helpers.id_utils import get_display_name_async
            from core.helpers.priority_utils import format_priority_log
            chat_display = await get_display_name_async(event.chat_id)
            p_desc = format_priority_log(final_priority, event.chat_id)
            logger.info(f"✅ [监听器] 普通消息已写入队列: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 优先级={p_desc}, 分组ID={event.message.grouped_id}")
        except Exception as e:
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.error(f"❌ [监听器] 消息处理失败: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 错误={str(e)}", exc_info=True)

    
    # 机器人客户端监听器 - 只处理命令
    @bot_client.on(events.NewMessage)
    async def bot_message_listener(event):
        """机器人消息监听器 - 只处理命令"""
        try:
            sleep_manager.record_activity()
            # 过滤机器人自己发送的消息 (防自环)
            if event.out or event.sender_id == bot_id:
                return

            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.info(f"🤖 [Bot监听器] 收到Bot命令: 来源={chat_display}({event.chat_id}), 发送者ID={event.sender_id}, 命令={event.text}")
            
            # 机器人命令直接调用处理函数，不写入队列
            from handlers import bot_handler
            await bot_handler.handle_command(bot_client, event)
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.info(f"✅ [Bot监听器] Bot命令处理完成: 来源={chat_display}({event.chat_id}), 命令={event.text}")
        except Exception as e:
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.error(f"❌ [Bot监听器] Bot命令处理失败: 来源={chat_display}({event.chat_id}), 命令={event.text}, 错误={str(e)}", exc_info=True)
    
    # 注册机器人回调处理器
    from handlers import bot_handler as bot_handler_module
    bot_client.add_event_handler(bot_handler_module.callback_handler)
    
    logger.info("统一消息监听器设置完成")
    logger.info("- 用户消息监听器：处理转发规则")
    logger.info("- 机器人消息监听器：处理命令和设置")
    logger.info("- 回调处理器：处理内联按钮回调")
