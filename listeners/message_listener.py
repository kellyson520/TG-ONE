"""
统一消息监听器

整合原有两个版本的优点，使用端口/适配器模式分离框架事件和业务处理。
提供清晰的监听器设置接口。
"""

from __future__ import annotations
import logging
from typing import Any

from telethon import events
from dotenv import load_dotenv

from core.container import container

# 加载环境变量
load_dotenv()

# 获取logger
logger = logging.getLogger(__name__)


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
        # 继续运行，但可能无法过滤机器人消息
    
    # 优化的消息过滤函数：区分命令和普通消息
    def should_process(event):
        # 不处理机器人自己发送的消息
        if event.sender_id == bot_id:
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
    
    # 用户客户端监听器 - 只写入任务队列
    @user_client.on(events.NewMessage(func=should_process))
    async def user_message_listener(event):
        """用户消息监听器 - 只写入任务队列"""
        try:
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.info(f"📥 [监听器] 收到新消息: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 发送者ID={event.sender_id}, 媒体={bool(event.message.media)}")
            
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
                    chat_display = await get_display_name_async(event.chat_id)
                    logger.info(f"🚀 [监听器] 手动下载任务已写入队列: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 优先级=100")
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
            # 写入背压消息队列 (Default Priority = 0)
            await container.queue_service.enqueue(
                ("process_message", payload, 0)
            )
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.info(f"✅ [监听器] 普通消息已写入队列: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 优先级=0, 分组ID={event.message.grouped_id}")
        except Exception as e:
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(event.chat_id)
            logger.error(f"❌ [监听器] 消息处理失败: 来源={chat_display}({event.chat_id}), 消息ID={event.id}, 错误={str(e)}", exc_info=True)

    
    # 机器人客户端监听器 - 只处理命令
    @bot_client.on(events.NewMessage)
    async def bot_message_listener(event):
        """机器人消息监听器 - 只处理命令"""
        try:
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
