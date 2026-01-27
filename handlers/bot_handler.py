from datetime import datetime, timedelta

import logging
import os
from dotenv import load_dotenv
from telethon import events
from telethon.tl.types import ChannelParticipantsAdmins
from version import WELCOME_TEXT

from core.constants import TEMP_DIR

# [Refactor Fix] 修正 utils 导入
from core.helpers.common import *
from core.helpers.media.media import *

# [Refactor Fix] 更新内部模块导入路径
from .button.callback.callback_handlers import handle_callback
from .command_handlers import *
from .link_handlers import handle_message_link

logger = logging.getLogger(__name__)

# 确保 temp 目录存在
os.makedirs(TEMP_DIR, exist_ok=True)

load_dotenv()


async def handle_command(client, event):
    """处理机器人命令"""
    import uuid
    from core.context import trace_id_var
    
    # 注入 Trace ID
    trace_id = str(uuid.uuid4())
    token = trace_id_var.set(trace_id)
    
    try:
        # 基本信息记录
        message = event.message
        user_id = event.sender_id
        chat_id = event.chat_id
        
        logger.info(f"🤖 [Bot命令] 收到命令请求: TraceID={trace_id}, 用户ID={user_id}, 聊天ID={chat_id}, 内容={message.text}")
        
        # 检查是否是管理员
        if not await is_admin(event):
            logger.warning(f"🚫 [Bot命令] 非管理员尝试执行命令: TraceID={trace_id}, 用户ID={user_id}, 命令={message.text}")
            return

        # 处理命令逻辑
        if not message.text:
            logger.debug(f"⚠️ [Bot命令] 空消息，跳过处理: TraceID={trace_id}")
            return

        chat = await event.get_chat()
        bot_user_id = await get_user_id()
        chat_id = abs(chat.id)
        bot_user_id = int(bot_user_id)

        # 链接转发功能 - 仅当消息以 / 开头时不处理链接
        if not message.text.startswith("/") and chat_id == bot_user_id:
            logger.info(f"🔗 [Bot命令] 进入链接转发功能: TraceID={trace_id}, 内容={message.text}")
            if "t.me/" in message.text:
                await handle_message_link(client, event)
                logger.info(f"✅ [Bot命令] 链接转发处理完成: TraceID={trace_id}")
            return

        # 只有以 / 开头的消息才被认为是命令
        if not message.text.startswith("/"):
            logger.debug(f"⚠️ [Bot命令] 非命令消息，跳过处理: TraceID={trace_id}, 内容={message.text}")
            return

        logger.info(f"📋 [Bot命令] 处理管理员命令: TraceID={trace_id}, 命令={event.message.text}")
        parts = message.text.split()
        raw_command = parts[0]
        command = parts[0].split("@")[0][1:]
        
        logger.debug(f"🔍 [Bot命令] 解析命令: TraceID={trace_id}, 原始命令={raw_command}, 解析后={command}, 参数={parts[1:]}")

        command_handlers = {
            "bind": lambda: handle_bind_command(event, client, parts),
            "b": lambda: handle_bind_command(event, client, parts),
            "settings": lambda: handle_settings_command(event, command, parts),
            "s": lambda: handle_settings_command(event, command, parts),
            "switch": lambda: handle_switch_command(event),
            "sw": lambda: handle_switch_command(event),
            "add": lambda: handle_add_command(event, command, parts),
            "a": lambda: handle_add_command(event, command, parts),
            "add_regex": lambda: handle_add_command(event, command, parts),
            "ar": lambda: handle_add_command(event, "add_regex", parts),
            "replace": lambda: handle_replace_command(event, parts),
            "r": lambda: handle_replace_command(event, parts),
            "list_keyword": lambda: handle_list_keyword_command(event),
            "lk": lambda: handle_list_keyword_command(event),
            "list_replace": lambda: handle_list_replace_command(event),
            "lrp": lambda: handle_list_replace_command(event),
            "remove_keyword": lambda: handle_remove_command(event, command, parts),
            "rk": lambda: handle_remove_command(event, "remove_keyword", parts),
            "remove_keyword_by_id": lambda: handle_remove_command(event, command, parts),
            "rkbi": lambda: handle_remove_command(event, "remove_keyword_by_id", parts),
            "remove_replace": lambda: handle_remove_command(event, command, parts),
            "rr": lambda: handle_remove_command(event, "remove_replace", parts),
            "remove_all_keyword": lambda: handle_remove_all_keyword_command(event, command, parts),
            "rak": lambda: handle_remove_all_keyword_command(event, "remove_all_keyword", parts),
            "clear_all": lambda: handle_clear_all_command(event),
            "ca": lambda: handle_clear_all_command(event),
            "start": lambda: handle_start_command(event),
            "help": lambda: handle_help_command(event, "help"),
            "h": lambda: handle_help_command(event, "help"),
            "export_keyword": lambda: handle_export_keyword_command(event, command),
            "ek": lambda: handle_export_keyword_command(event, command),
            "export_replace": lambda: handle_export_replace_command(event, client),
            "er": lambda: handle_export_replace_command(event, client),
            "add_all": lambda: handle_add_all_command(event, command, parts),
            "aa": lambda: handle_add_all_command(event, "add_all", parts),
            "add_regex_all": lambda: handle_add_all_command(event, command, parts),
            "ara": lambda: handle_add_all_command(event, "add_regex_all", parts),
            "replace_all": lambda: handle_replace_all_command(event, parts),
            "ra": lambda: handle_replace_all_command(event, parts),
            "import_keyword": lambda: handle_import_command(event, command),
            "ik": lambda: handle_import_command(event, "import_keyword"),
            "import_regex_keyword": lambda: handle_import_command(event, command),
            "irk": lambda: handle_import_command(event, "import_regex_keyword"),
            "import_replace": lambda: handle_import_command(event, command),
            "ir": lambda: handle_import_command(event, "import_replace"),
            "import_excel": lambda: handle_import_excel_command(event),
            "forward_stats": lambda: handle_forward_stats_command(event, command),
            "fs": lambda: handle_forward_stats_command(event, command),
            "forward_search": lambda: handle_forward_search_command(event, command),
            "fsr": lambda: handle_forward_search_command(event, command),
            "ufb_bind": lambda: handle_ufb_bind_command(event, command),
            "ub": lambda: handle_ufb_bind_command(event, "ufb_bind"),
            "ufb_unbind": lambda: handle_ufb_unbind_command(event, command),
            "uu": lambda: handle_ufb_unbind_command(event, "ufb_unbind"),
            "ufb_item_change": lambda: handle_ufb_item_change_command(event, command),
            "uic": lambda: handle_ufb_item_change_command(event, "ufb_item_change"),
            "clear_all_keywords": lambda: handle_clear_all_keywords_command(event, command),
            "cak": lambda: handle_clear_all_keywords_command(event, "clear_all_keywords"),
            "clear_all_keywords_regex": lambda: handle_clear_all_keywords_regex_command(event, command),
            "cakr": lambda: handle_clear_all_keywords_regex_command(event, "clear_all_keywords_regex"),
            "clear_all_replace": lambda: handle_clear_all_replace_command(event, command),
            "car": lambda: handle_clear_all_replace_command(event, "clear_all_replace"),
            "copy_keywords": lambda: handle_copy_keywords_command(event, command),
            "ck": lambda: handle_copy_keywords_command(event, "copy_keywords"),
            "copy_keywords_regex": lambda: handle_copy_keywords_regex_command(event, command),
            "ckr": lambda: handle_copy_keywords_regex_command(event, "copy_keywords_regex"),
            "copy_replace": lambda: handle_copy_replace_command(event, command),
            "crp": lambda: handle_copy_replace_command(event, "copy_replace"),
            "copy_rule": lambda: handle_copy_rule_command(event, command),
            "cr": lambda: handle_copy_rule_command(event, "copy_rule"),
            "changelog": lambda: handle_changelog_command(event),
            "cl": lambda: handle_changelog_command(event),
            "list_rule": lambda: handle_list_rule_command(event, command, parts),
            "lr": lambda: handle_list_rule_command(event, command, parts),
            "search": lambda: handle_search_command(event, command, parts),
            "search_bound": lambda: handle_search_bound_command(event, command, parts),
            "sb": lambda: handle_search_bound_command(event, "search_bound", parts),
            "search_public": lambda: handle_search_public_command(event, command, parts),
            "sp": lambda: handle_search_public_command(event, "search_public", parts),
            "search_all": lambda: handle_search_all_command(event, command, parts),
            "sa": lambda: handle_search_all_command(event, "search_all", parts),
            "delete_rule": lambda: handle_delete_rule_command(event, command, parts),
            "dr": lambda: handle_delete_rule_command(event, command, parts),
            "delete_rss_user": lambda: handle_delete_rss_user_command(event, command, parts),
            "dru": lambda: handle_delete_rss_user_command(event, command, parts),
            "dedup": lambda: handle_dedup_enable_command(event, parts),
            "dedup_scan": lambda: handle_dedup_scan_command(event, parts),
            "db_info": lambda: handle_db_info_command(event),
            "db_backup": lambda: handle_db_backup_command(event),
            "db_optimize": lambda: handle_db_optimize_command(event),
            "db_health": lambda: handle_db_health_command(event),
            "video_cache_stats": lambda: handle_video_cache_stats_command(event),
            "video_cache_clear": lambda: handle_video_cache_clear_command(event, parts),
            "system_status": lambda: handle_system_status_command(event),
            "admin": lambda: handle_admin_panel_command(event),
            "set_duration": lambda: handle_set_duration_command(event, parts),
            "set_resolution": lambda: handle_set_resolution_command(event, parts),
            "set_size": lambda: handle_set_size_command(event, parts),
        }

        handler = command_handlers.get(command)
        if handler:
            logger.info(f"🚀 [Bot命令] 执行命令: TraceID={trace_id}, 命令={command}")
            await handler()
            logger.info(f"✅ [Bot命令] 命令执行完成: TraceID={trace_id}, 命令={command}")
        else:
            logger.warning(f"❓ [Bot命令] 未知命令: TraceID={trace_id}, 命令={command}")
            await event.respond("未知命令，请使用 /help 查看帮助")
    except Exception as e:
        logger.error(f"❌ [Bot命令] 处理命令失败: TraceID={trace_id}, 命令={message.text if message else '未知'}, 错误={str(e)}", exc_info=True)
        # 向用户发送错误信息
        await event.respond(f"处理命令时出错: {str(e)}")
    finally:
        trace_id_var.reset(token)
        logger.debug(f"🔚 [Bot命令] 请求处理结束: TraceID={trace_id}")


# 注册回调处理器
@events.register(events.CallbackQuery)
async def callback_handler(event):
    """回调处理器入口"""
    import uuid
    from core.context import trace_id_var
    
    # 注入 Trace ID
    trace_id = str(uuid.uuid4())
    token = trace_id_var.set(trace_id)
    
    try:
        # 检查是否是管理员的回调
        if not await is_admin(event):
            return
        await handle_callback(event)
    except Exception as e:
        logger.error(f"处理回调时出错: {e}", exc_info=True)
    finally:
        trace_id_var.reset(token)


async def send_welcome_message(client):
    """发送欢迎消息"""
    user_id = await get_user_id()

    try:
        from telethon.errors import FloodWaitError
        # 发送新消息
        await client.send_message(
            user_id, WELCOME_TEXT, parse_mode="html", link_preview=True
        )
        logger.info("已发送欢迎消息")
    except FloodWaitError as e:
        logger.warning(f"发送欢迎消息失败，需等待 {e.seconds} 秒: {e}")
    except Exception as e:
        logger.warning(f"发送欢迎消息失败: {e}")
