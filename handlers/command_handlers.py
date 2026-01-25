import shlex
import traceback

import asyncio
import os
import re
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from telethon import Button, events
from version import UPDATE_INFO, VERSION

import models.models as models
from enums.enums import AddMode, ForwardMode

# 导入状态管理相关功能
# 使用 session_manager 替代已废弃的 state_manager
from handlers.button.session_management import session_manager
from handlers.button.settings_manager import create_buttons, create_settings_text
from handlers.list_handlers import *
from models.models import (
    Chat,
    ForwardRule,
    Keyword,
    MediaExtensions,
    MediaTypes,
    ReplaceRule,
    RuleSync,
    User,
)
from utils.processing.auto_delete import (
    async_delete_user_message,
    reply_and_delete,
    respond_and_delete,
)
from utils.helpers.common import *
from utils.helpers.common import get_bot_client

# aiohttp 在某些环境未安装会导致编辑器提示，这里保留在使用处延迟导入
from utils.core.constants import *

# 延迟导入避免循环依赖
from utils.media.excel_importer import parse_excel
from utils.forward_recorder import forward_recorder
from utils.media import *


# 全局命令注册函数
async def register_handlers(client):
    """注册所有命令处理器"""

    @client.on(events.NewMessage(pattern="/download"))
    async def download_handler(event):
        """处理 /download 指令，设置用户状态为等待文件"""
        # 设置用户状态为等待文件
        # 使用 session_manager 替代已废弃的 state_manager
        if event.sender_id not in session_manager.user_sessions:
            session_manager.user_sessions[event.sender_id] = {}
        session_manager.user_sessions[event.sender_id][event.chat_id] = {
            "state": "waiting_for_file"
        }
        await reply_and_delete(
            event,
            "📥 **进入下载模式**\n请发送您想要下载的文件、视频或图片。\n发送 /cancel 取消。",
        )

    @client.on(events.NewMessage(pattern="/cancel"))
    async def cancel_handler(event):
        """处理 /cancel 指令，取消下载模式"""
        # 清除用户状态
        # 使用 session_manager 替代已废弃的 state_manager
        if event.sender_id in session_manager.user_sessions:
            if event.chat_id in session_manager.user_sessions[event.sender_id]:
                session_manager.user_sessions[event.sender_id].pop(event.chat_id)
                # 如果用户会话为空，清理掉该用户的会话记录
                if not session_manager.user_sessions[event.sender_id]:
                    session_manager.user_sessions.pop(event.sender_id)
        await reply_and_delete(event, "已退出下载模式。")

    @client.on(events.NewMessage(pattern="/download"))
    async def download_handler(event):
        await handle_download_command(event, client, event.message.text.split())

    @client.on(events.NewMessage(pattern="/logs"))
    async def logs_handler_wrapper(event):
         await handle_logs_command(event, event.message.text.split())

    @client.on(events.NewMessage(pattern="/download_logs"))
    async def download_logs_handler_wrapper(event):
         await handle_download_logs_command(event, event.message.text.split())

    @client.on(events.NewMessage(pattern="/db_optimize"))
    async def db_optimize_handler_wrapper(event):
         await handle_db_optimize_command(event)

    @client.on(events.NewMessage(pattern="/db_info"))
    async def db_info_handler_wrapper(event):
         await handle_db_info_command(event)

    @client.on(events.NewMessage(pattern="/db_backup"))
    async def db_backup_handler_wrapper(event):
         await handle_db_backup_command(event)
         
    @client.on(events.NewMessage(pattern="/db_health"))
    async def db_health_handler_wrapper(event):
         await handle_db_health_command(event)

    @client.on(events.NewMessage(pattern="/system_status"))
    async def system_status_handler_wrapper(event):
         await handle_system_status_command(event)

    @client.on(events.NewMessage(pattern="/admin"))
    async def admin_panel_handler_wrapper(event):
         await handle_admin_panel_command(event)

    @client.on(events.NewMessage(pattern="/video_cache_stats"))
    async def video_cache_stats_handler_wrapper(event):
         await handle_video_cache_stats_command(event)

    @client.on(events.NewMessage(pattern="/video_cache_clear"))
    async def video_cache_clear_handler_wrapper(event):
         await handle_video_cache_clear_command(event, event.message.text.split())

    @client.on(events.NewMessage(pattern="/dedup_scan"))
    async def dedup_scan_handler_wrapper(event):
         await handle_dedup_scan_command(event, event.message.text.split())

    @client.on(events.NewMessage(pattern="/dedup"))
    async def dedup_handler_wrapper(event):
         await handle_dedup_command(event)



# 导入容器实例
# 导入容器实例
# from core.container import container (moved to local scopes)

# 导入统一优化工具
from utils.core.error_handler import handle_errors, handle_telegram_errors, retry_on_failure
from utils.core.logger_utils import get_logger, log_performance, log_user_action
from utils.helpers.message_utils import get_message_handler
from utils.processing.unified_cache import cached, get_smart_cache

logger = get_logger(__name__)

# [P2 Refactor] 引入业务服务层
from services.rule_management_service import rule_management_service
from services.rule_service import RuleQueryService

# =============== 高级媒体筛选 - 命令式设置 ===============


async def _get_current_rule_for_chat(session, event):
    """根据当前聊天获取当前规则 - 适配 RuleQueryService"""
    return await RuleQueryService.get_current_rule_for_chat(event, session)


async def handle_set_duration_command(event, parts):
    """/set_duration <min> [max]"""
    # 从container获取数据库会话
    from core.container import container
    async with container.db.session() as session:
        try:
            rule = await _get_current_rule_for_chat(session, event)
            if not rule:
                await reply_and_delete(
                    event, "❌ 未找到当前聊天的规则，请先 /switch 选择源聊天"
                )
                return
            if len(parts) < 2:
                await reply_and_delete(
                    event,
                    "用法: /set_duration <最小秒> [最大秒]\n示例: /set_duration 30 300 或 /set_duration 0 300 或 /set_duration 30",
                )
                return
            try:
                min_val = int(parts[1])
                max_val = (
                    int(parts[2])
                    if len(parts) >= 3
                    else getattr(rule, "max_duration", 0)
                )
            except ValueError:
                await reply_and_delete(event, "❌ 参数必须为整数")
                return
            if min_val < 0 or max_val < 0:
                await reply_and_delete(event, "❌ 时长不能为负数")
                return
            if max_val > 0 and min_val > max_val:
                await reply_and_delete(event, "❌ 最小时长不能大于最大时长")
                return
            rule.enable_duration_filter = True
            rule.min_duration = min_val
            rule.max_duration = max_val
            await session.commit()
            await reply_and_delete(
                event,
                f"✅ 时长范围已设置为: {min_val}s - {max_val if max_val>0 else '∞'}s",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"设置时长范围失败: {str(e)}")
            await reply_and_delete(event, "❌ 设置时长范围失败，请检查日志")


async def handle_set_resolution_command(event, parts):
    """/set_resolution <min_w> <min_h> [max_w] [max_h]"""
    # 从container获取数据库会话
    from core.container import container
    async with container.db.session() as session:
        try:
            rule = await _get_current_rule_for_chat(session, event)
            if not rule:
                await reply_and_delete(
                    event, "❌ 未找到当前聊天的规则，请先 /switch 选择源聊天"
                )
                return
            if len(parts) not in (3, 5):
                await reply_and_delete(
                    event,
                    "用法: /set_resolution <最小宽> <最小高> [最大宽] [最大高]\n示例: /set_resolution 720 480 1920 1080 或 /set_resolution 720 480",
                )
                return
            try:
                min_w = int(parts[1])
                min_h = int(parts[2])
                max_w = (
                    int(parts[3]) if len(parts) >= 5 else getattr(rule, "max_width", 0)
                )
                max_h = (
                    int(parts[4]) if len(parts) >= 5 else getattr(rule, "max_height", 0)
                )
            except ValueError:
                await reply_and_delete(event, "❌ 参数必须为整数")
                return
            if min_w < 0 or min_h < 0 or max_w < 0 or max_h < 0:
                await reply_and_delete(event, "❌ 分辨率不能为负数")
                return
            if max_w > 0 and min_w > max_w:
                await reply_and_delete(event, "❌ 最小宽度不能大于最大宽度")
                return
            if max_h > 0 and min_h > max_h:
                await reply_and_delete(event, "❌ 最小高度不能大于最大高度")
                return
            rule.enable_resolution_filter = True
            rule.min_width = min_w
            rule.min_height = min_h
            rule.max_width = max_w
            rule.max_height = max_h
            await session.commit()
            await reply_and_delete(
                event,
                f"✅ 分辨率范围已设置为: {min_w}x{min_h} - {max_w if max_w>0 else '∞'}x{max_h if max_h>0 else '∞'}",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"设置分辨率范围失败: {str(e)}")
            await reply_and_delete(event, "❌ 设置分辨率范围失败，请检查日志")


def _parse_size_to_kb(s: str) -> int:
    s = s.strip().upper()
    if s.endswith("G"):
        return int(float(s[:-1]) * 1024 * 1024)
    if s.endswith("M"):
        return int(float(s[:-1]) * 1024)
    if s.endswith("K") or s.endswith("KB"):
        return int(float(s.rstrip("KB")))
    return int(s)


async def handle_set_size_command(event, parts):
    """/set_size <min> [max]，支持K/M/G单位"""
    # 从container获取数据库会话
    from core.container import container
    async with container.db.session() as session:
        try:
            rule = await _get_current_rule_for_chat(session, event)
            if not rule:
                await reply_and_delete(
                    event, "❌ 未找到当前聊天的规则，请先 /switch 选择源聊天"
                )
                return
            if len(parts) < 2:
                await reply_and_delete(
                    event,
                    "用法: /set_size <最小大小> [最大大小]\n示例: /set_size 10M 200M 或 /set_size 1024 20480 或 /set_size 0 200M",
                )
                return
            try:
                min_kb = _parse_size_to_kb(parts[1])
                max_kb = (
                    _parse_size_to_kb(parts[2])
                    if len(parts) >= 3
                    else getattr(rule, "max_file_size", 0)
                )
            except ValueError:
                await reply_and_delete(event, "❌ 大小参数格式错误，支持K/M/G单位")
                return
            if min_kb < 0 or max_kb < 0:
                await reply_and_delete(event, "❌ 文件大小不能为负数")
                return
            if max_kb > 0 and min_kb > max_kb:
                await reply_and_delete(event, "❌ 最小大小不能大于最大大小")
                return
            rule.enable_file_size_range = True
            rule.min_file_size = min_kb
            rule.max_file_size = max_kb
            await session.commit()

            def _fmt(kb: int):
                if kb >= 1024 * 1024:
                    return f"{kb/1024/1024:.1f}GB"
                if kb >= 1024:
                    return f"{kb/1024:.1f}MB"
                return f"{kb}KB"

            await reply_and_delete(
                event,
                f"✅ 文件大小范围已设置为: {_fmt(min_kb)} - {_fmt(max_kb) if max_kb>0 else '∞'}",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"设置文件大小范围失败: {str(e)}")
            await reply_and_delete(event, "❌ 设置文件大小范围失败，请检查日志")


async def handle_bind_command(event, client, parts):
    """处理 bind 命令 - 业务逻辑已迁移至 RuleManagementService"""
    message_text = event.message.text
    try:
        # 1. 参数解析
        if " " in message_text:
            command, args_str = message_text.split(" ", 1)
            args = shlex.split(args_str)
            if len(args) >= 1:
                source_input = args[0]
                target_input = args[1] if len(args) >= 2 else None
            else:
                raise ValueError("参数不足")
        else:
            raise ValueError("参数不足")
    except ValueError:
        await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
        await reply_and_delete(
            event,
            '用法: /bind <源聊天链接或名称> [目标聊天链接或名称]\n例如:\n/bind https://t.me/channel_name\n/bind "频道 名称"\n/bind https://t.me/source_channel https://t.me/target_channel',
        )
        return

    # 2. 调用服务层
    from core.container import container
    user_client = container.user_client
    result = await rule_management_service.bind_chat(
        user_client, 
        source_input, 
        target_input, 
        current_chat_id=event.chat_id
    )

    # 3. 处理结果
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    
    if result.get('success'):
        msg = (
            f"✅ {'已创建' if result.get('is_new') else '已找到存在'}的转发规则:\n"
            f"源聊天: {result.get('source_name')}\n"
            f"目标聊天: {result.get('target_name')}\n"
            f"请使用 /add 或 /add_regex 添加关键字"
        )
        buttons = [Button.inline("⚙️ 打开设置", f"rule_settings:{result.get('rule_id')}")]
        await reply_and_delete(event, msg, buttons=buttons)
    else:
        await reply_and_delete(event, f"❌ 绑定失败: {result.get('error')}")


@log_performance("处理设置命令", threshold_seconds=3.0)
@log_user_action(
    "设置",
    extract_user_id=lambda event, command, parts: getattr(
        event.sender, "id", "unknown"
    ),
)
@handle_errors(default_return=None)
async def handle_settings_command(event, command, parts):
    """处理 settings 命令 - 启动新菜单系统 - 优化版本"""
    logger.log_operation("处理设置命令", details=f"命令: {command}")

    # 显示新的主菜单（延迟导入避免循环依赖）
    from .button.new_menu_system import new_menu_system

    await new_menu_system.show_main_menu(event)

    # 在菜单显示成功后删除用户消息
    try:
        await async_delete_user_message(
            event.client, event.message.chat_id, event.message.id, 0
        )
        logger.log_operation("设置命令处理完成", details="菜单显示成功，用户消息已删除")
    except Exception as e:
        logger.log_error("删除用户消息", e)


@log_performance("处理切换命令", threshold_seconds=3.0)
@log_user_action(
    "切换规则", extract_user_id=lambda event: getattr(event.sender, "id", "unknown")
)
@handle_errors(default_return=None)
async def handle_switch_command(event):
    """处理 switch 命令 - 使用 RuleQueryService 优化交互"""
    current_chat = await event.get_chat()
    current_chat_id = current_chat.id

    logger.log_operation("处理切换命令", details=f"聊天ID: {current_chat_id}")

    # 1. 调用服务层获取作为目标的所有规则
    rules = await RuleQueryService.get_rules_for_target_chat(current_chat_id)

    if not rules:
        await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
        await reply_and_delete(
            event,
            "❌ 当前聊天没有任何转发规则\n提示：使用 /bind @源聊天 来创建规则，或在目标聊天中使用此命令",
        )
        return

    # 2. 获取当前聊天记录以确定选中的规则
    from core.container import container
    async with container.db.session() as session:
        from models.models import Chat
        from sqlalchemy import select
        stmt = select(Chat).where(Chat.telegram_chat_id == str(current_chat_id))
        result = await session.execute(stmt)
        current_chat_db = result.scalar_one_or_none()

    # 3. 创建规则选择按钮
    buttons = []
    for rule in rules:
        source_chat = rule.source_chat
        if not source_chat:
            continue

        is_current = False
        if (
            current_chat_db
            and current_chat_db.current_add_id == source_chat.telegram_chat_id
        ):
            is_current = True

        button_text = f'{"✓ " if is_current else ""}来自: {source_chat.name}'
        callback_data = f"switch:{source_chat.telegram_chat_id}"
        buttons.append([Button.inline(button_text, callback_data)])

    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    await reply_and_delete(event, "请选择要管理的转发规则:", buttons=buttons)


@log_performance("添加关键字", threshold_seconds=5.0)
async def _parse_keywords(message_text, command, parts, event):
    """解析关键字，处理引号"""
    try:
        # 移除命令部分
        if " " not in message_text:
            return []
        _, args_text = message_text.split(None, 1)
        if command == "add" or command == "add_all":
            return shlex.split(args_text)
        else: # add_regex 或 add_regex_all
            # 正则表达式通常不使用 shlex 分割，以防特殊字符被转义
            # 这里简单按空格分割，或者如果报错则整体作为一个
            try:
                kw_list = args_text.split()
                return kw_list if kw_list else [args_text]
            except Exception:
                return [args_text]
    except Exception as e:
        logger.error(f"解析参数失败: {e}")
        from utils.processing.auto_delete import reply_and_delete
        await reply_and_delete(event, "参数格式错误：请确认引号是否正确配对")
        return []


async def _add_keywords_to_rule(keywords, command, event):
    """通用逻辑：获取当前规则并将关键字加入"""
    from core.container import container
    from enums.enums import AddMode
    from services.rule_service import RuleQueryService
    from services.rule_management_service import rule_management_service

    from utils.processing.auto_delete import reply_and_delete

    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return None
        rule, source_chat = rule_info
        
        is_regex = "regex" in command
        is_blacklist = rule.add_mode == AddMode.BLACKLIST
        
        result = await rule_management_service.add_keywords(
            rule_id=rule.id,
            keywords=keywords,
            is_regex=is_regex,
            is_negative=is_blacklist
        )
        return rule, source_chat, result


@log_user_action(
    "添加关键字",
    extract_user_id=lambda event, command, parts: getattr(
        event.sender, "id", "unknown"
    ),
)
@handle_errors(default_return=None)
async def handle_add_command(event, command, parts):
    """处理 add 和 add_regex 命令 - 优化版本"""
    message_text = event.message.text
    logger.log_operation("处理添加关键字命令", details=f"命令: {command}")

    # 验证参数
    if len(message_text.split(None, 1)) < 2:
        await async_delete_user_message(
            event.client, event.message.chat_id, event.message.id, 0
        )
        await reply_and_delete(
            event,
            f"用法: /{command} <关键字1> [关键字2] ...\n例如:\n/{command} keyword1 \"key word 2\" 'key word 3'",
        )
        return

    # 解析关键字
    keywords = await _parse_keywords(message_text, command, parts, event)
    if not keywords:
        return

    # 获取当前规则并添加关键字
    result = await _add_keywords_to_rule(keywords, command, event)
    if result:
        rule, source_chat, add_result = result

        # 发送结果消息
        await reply_and_delete(
            event, 
            add_result.get('message', '关键字添加成功')
        )


async def handle_replace_command(event, parts):
    """处理 replace 命令 - 业务逻辑已迁移至 RuleManagementService"""
    message_text = event.message.text
    try:
        _, args_text = message_text.split(None, 1)
        r_parts = args_text.split(None, 1)
        pattern = r_parts[0]
        content = r_parts[1] if len(r_parts) > 1 else ""
    except Exception:
        await reply_and_delete(event, "用法: /replace <匹配规则> [替换内容]")
        return

    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        
        result = await container.rule_management_service.add_replace_rules(
            rule_id=rule.id,
            patterns=[pattern],
            replacements=[content],
            is_regex=False
        )
    
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        action = "删除" if not content else "替换"
        msg = f"✅ 已添加替换规则到 {source_chat.name}:\n匹配: {pattern}\n动作: {action}\n"
        if content:
             msg += f"替换为: {content}"
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 添加替换规则失败: {result.get('error')}")


async def handle_list_keyword_command(event):
    """处理 list_keyword 命令 - 使用统一 Service 获取规则"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info

        from models.models import Keyword
        is_blacklist = rule.add_mode == AddMode.BLACKLIST
        stmt = select(Keyword).filter_by(rule_id=rule.id, is_blacklist=is_blacklist).order_by(Keyword.id)
        keywords = (await session.execute(stmt)).scalars().all()

    if not keywords:
        await reply_and_delete(event, f"提示：当前规则 ({source_chat.name}) 没有任何关键字。")
        return

    mode_str = "黑名单" if is_blacklist else "白名单"
    res_text = f"📋 **{source_chat.name} 的关键字列表 ({mode_str}):**\n\n"
    for i, kw in enumerate(keywords, 1):
        type_str = "[正则] " if kw.is_regex else ""
        res_text += f"{i}. {type_str}`{kw.keyword}`\n"

    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    await reply_and_delete(event, res_text)


async def handle_list_replace_command(event):
    """处理 list_replace 命令 - 使用统一 Service 获取规则"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info

        from models.models import ReplaceRule
        stmt = select(ReplaceRule).filter_by(rule_id=rule.id).order_by(ReplaceRule.id)
        replace_rules = (await session.execute(stmt)).scalars().all()

    if not replace_rules:
        await reply_and_delete(event, f"提示：当前规则 ({source_chat.name}) 没有任何替换规则。")
        return

    res_text = f"📋 **{source_chat.name} 的替换规则列表:**\n\n"
    for i, r in enumerate(replace_rules, 1):
        action = "删除" if not r.content else f"替换为 `{r.content}`"
        res_text += f"{i}. 匹配 `{r.pattern}` -> {action}\n"

    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    await reply_and_delete(event, res_text)


async def handle_remove_command(event, command, parts):
    """处理 remove_keyword 和 remove_replace 命令 - 业务逻辑已迁移至 RuleManagementService"""
    message_text = event.message.text
    ids_to_remove = []
    keywords_to_remove = []

    # 1. 参数解析
    is_remove_by_id = command in ["remove_replace", "remove_keyword_by_id", "rkbi"]
    if is_remove_by_id:
        if len(parts) < 2:
            await reply_and_delete(event, f"用法: /{command} <序号1> [序号2] ...")
            return
        try:
            ids_to_remove = [int(x) for x in parts[1:]]
        except ValueError:
            await reply_and_delete(event, "序号必须是数字")
            return
    elif command == "remove_keyword":
        try:
            _, args_text = message_text.split(None, 1)
            keywords_to_remove = shlex.split(args_text)
        except Exception:
            await reply_and_delete(event, f"用法: /{command} <关键字1> ...")
            return

    # 2. 获取规则上下文
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        
        # 3. 处理按序号删除的映射 (序号 -> 真实内容)
        if is_remove_by_id:
            from models.models import Keyword, ReplaceRule
            if command in ["remove_keyword_by_id", "rkbi"]:
                is_blacklist = rule.add_mode == AddMode.BLACKLIST
                stmt = select(Keyword).filter_by(rule_id=rule.id, is_blacklist=is_blacklist).order_by(Keyword.id)
                items = (await session.execute(stmt)).scalars().all()
                targets = [items[i-1].keyword for i in ids_to_remove if 1 <= i <= len(items)]
                if targets:
                    result = await container.rule_management_service.delete_keywords(rule.id, targets)
                else:
                    await reply_and_delete(event, "❌ 无效序号")
                    return
            else: # remove_replace
                stmt = select(ReplaceRule).filter_by(rule_id=rule.id).order_by(ReplaceRule.id)
                items = (await session.execute(stmt)).scalars().all()
                targets = [items[i-1].pattern for i in ids_to_remove if 1 <= i <= len(items)]
                if targets:
                    result = await container.rule_management_service.delete_replace_rules(rule.id, targets)
                else:
                    await reply_and_delete(event, "❌ 无效序号")
                    return
        else: # remove_keyword (by text)
            result = await container.rule_management_service.delete_keywords(rule.id, keywords_to_remove)

    # 4. 反馈结果
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        await reply_and_delete(event, f"✅ 已成功删除指定项目")
    else:
        await reply_and_delete(event, f"❌ 删除失败: {result.get('error')}")


async def handle_clear_all_command(event):
    """处理 clear_all 命令 - 使用 RuleManagementService"""
    # 这里通常应该增加一个二次确认逻辑，但为了保持逻辑一致，我们先直接迁移
    result = await rule_management_service.clear_all_data()

    if result.get('success'):
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, f"✅ {result['message']}")
    else:
        await reply_and_delete(event, f"❌ 清空数据失败: {result.get('error', '未知错误')}")


async def handle_changelog_command(event):
    """处理 changelog 命令"""
    await async_delete_user_message(
        event.client, event.message.chat_id, event.message.id, 0
    )
    await reply_and_delete(event, UPDATE_INFO, parse_mode="html")


async def handle_start_command(event):
    """处理 start 命令"""

    welcome_text = f"""
    👋 欢迎使用 Telegram 消息转发机器人！
    
    📱 当前版本：v{VERSION}

    📖 查看完整命令列表请使用 /help

    """
    await async_delete_user_message(
        event.client, event.message.chat_id, event.message.id, 0
    )
    await reply_and_delete(event, welcome_text)


async def handle_help_command(event, command):
    """处理帮助命令"""
    help_text = (
        f"🤖 **Telegram 消息转发机器人 v{VERSION}**\n\n"
        "**基础命令**\n"
        "/start - 开始使用\n"
        "/help(/h) - 显示此帮助信息\n\n"
        "**绑定和设置**\n"
        "/bind(/b) <源聊天链接或名称> [目标聊天链接或名称] - 绑定源聊天\n"
        "/settings(/s) [规则ID] - 管理转发规则\n"
        "/changelog(/cl) - 查看更新日志\n\n"
        "**转发规则管理**\n"
        "/copy_rule(/cr)  <源规则ID> [目标规则ID] - 复制指定规则的所有设置到当前规则或目标规则ID\n"
        "/list_rule(/lr) - 列出所有转发规则\n"
        "/delete_rule(/dr) <规则ID> [规则ID] [规则ID] ... - 删除指定规则\n\n"
        "**关键字管理**\n"
        "/add(/a) <关键字> [关键字] [\"关 键 字\"] ['关 键 字'] ... - 添加普通关键字\n"
        "/add_regex(/ar) <正则表达式> [正则表达式] [正则表达式] ... - 添加正则表达式\n"
        "/add_all(/aa) <关键字> [关键字] [关键字] ... - 添加普通关键字到当前频道绑定的所有规则\n"
        "/add_regex_all(/ara) <正则表达式> [正则表达式] [正则表达式] ... - 添加正则表达式到所有规则\n"
        "/list_keyword(/lk) - 列出所有关键字\n"
        "/remove_keyword(/rk) <关键词1> [\"关 键 字\"] ['关 键 字'] ... - 删除关键字\n"
        "/remove_keyword_by_id(/rkbi) <ID> [ID] [ID] ... - 按ID删除关键字\n"
        "/remove_all_keyword(/rak) [关键字] [\"关 键 字\"] ['关 键 字'] ... - 删除当前频道绑定的所有规则的指定关键字\n"
        "/clear_all_keywords(/cak) - 清除当前规则的所有关键字\n"
        "/clear_all_keywords_regex(/cakr) - 清除当前规则的所有正则关键字\n"
        "/copy_keywords(/ck) <规则ID> - 复制指定规则的关键字到当前规则\n"
        "/copy_keywords_regex(/ckr) <规则ID> - 复制指定规则的正则关键字到当前规则\n\n"
        "**替换规则管理**\n"
        "/replace(/r) <正则表达式> [替换内容] - 添加替换规则\n"
        "/replace_all(/ra) <正则表达式> [替换内容] - 添加替换规则到所有规则\n"
        "/list_replace(/lrp) - 列出所有替换规则\n"
        "/remove_replace(/rr) <序号> - 删除替换规则\n"
        "/clear_all_replace(/car) - 清除当前规则的所有替换规则\n"
        "/copy_replace(/crp) <规则ID> - 复制指定规则的替换规则到当前规则\n\n"
        "**导入导出**\n"
        "/export_keyword(/ek) - 导出当前规则的关键字\n"
        "/export_replace(/er) - 导出当前规则的替换规则\n"
        "/import_keyword(/ik) <同时发送文件> - 导入普通关键字\n"
        "/import_regex_keyword(/irk) <同时发送文件> - 导入正则关键字\n"
        "/import_replace(/ir) <同时发送文件> - 导入替换规则\n"
        "/import_excel <同时发送xlsx文件> - 一次性导入关键字与替换规则\n\n"
        "**转发记录查询**\n"
        "/forward_stats(/fs) [日期] - 查看转发统计 (如: /fs 2024-01-15)\n"
        "/forward_search(/fsr) [参数] - 搜索转发记录\n"
        "  参数格式: chat:聊天ID user:用户ID type:消息类型 rule:规则ID date:日期 limit:数量\n"
        "  例: /fsr chat:-1001234567 type:video limit:5\n\n"
        "**RSS相关**\n"
        "/delete_rss_user(/dru) [用户名] - 删除RSS用户\n"
        "**去重相关**\n"
        "/dedup - 切换当前规则的去重开关\n"
        "/dedup_scan - 扫描当前目标会话的重复媒体\n\n"
        "**数据库管理**\n"
        "/db_info - 查看数据库信息\n"
        "/db_backup - 备份数据库\n"
        "/db_optimize - 优化数据库\n"
        "/db_health - 数据库健康检查\n\n"
        "**系统管理**\n"
        "/system_status - 查看系统状态\n"
        "/admin - 系统管理面板\n"
        "/logs - 查看系统日志 (支持 error 参数查看错误日志)\n"
        "/download_logs - 下载完整系统日志\n\n"
        "**UFB相关**\n"
        "/ufb_bind(/ub) <域名> - 绑定UFB域名\n"
        "/ufb_unbind(/uu) - 解绑UFB域名\n"
        "/ufb_item_change(/uic) - 切换UFB同步配置类型\n\n"
        "💡 **提示**\n"
        "• 括号内为命令的简写形式\n"
        "• 尖括号 <> 表示必填参数\n"
        "• 方括号 [] 表示可选参数\n"
        "• 导入命令需要同时发送文件"
    )

    await async_delete_user_message(
        event.client, event.message.chat_id, event.message.id, 0
    )

    await async_delete_user_message(
        event.client, event.message.chat_id, event.message.id, 0
    )
    await reply_and_delete(event, help_text, parse_mode="markdown")


# =================== 去重命令实现 ===================
async def handle_dedup_enable_command(event, parts):
    """开启/关闭去重 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        
        current_val = getattr(rule, "enable_dedup", False)
        new_val = not current_val
    
    # 使用 Service 层更新去重设置
    result = await rule_management_service.update_rule(
        rule_id=rule.id,
        enable_dedup=new_val
    )
    
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        status = "开启" if new_val else "关闭"
        tip = "将自动跳过已存在的相同媒体" if new_val else "不再检查重复"
        await reply_and_delete(event, f"✅ 已{status}去重\n{tip}")
    else:
        await reply_and_delete(event, f"❌ 切换去重失败: {result.get('error')}")


async def handle_download_command(event, client, parts):
    """处理 download 命令 - 手动触发下载"""
    if not event.is_reply:
        await reply_and_delete(event, "请回复一条包含媒体的消息。")
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg.media:
        await reply_and_delete(event, "这条消息没有媒体文件。")
        return

    # 构造 Payload
    payload = {
        "chat_id": event.chat_id,
        "message_id": reply_msg.id,
        "manual_trigger": True,
    }

    # 写入任务队列，优先级 100 (插队)
    from core.container import container

    await container.task_repo.push(
        task_type="download_file",  # 注意这里用了专门的 download 类型
        payload=payload,
        priority=100,
    )

    await reply_and_delete(event, "✅ 已加入下载队列，即将开始...")


async def handle_dedup_scan_command(event, parts):
    """去重扫描 - 保持原有逻辑但增强安全性"""
    try:
        from handlers.button.session_management import session_manager

        # 确保 session_manager 内部实现了异步逻辑，这里只做调用保护
        chat_id = event.chat_id
        progress_msg = await event.respond("🚀 开始扫描重复消息...", parse_mode="md")

        async def progress_callback(processed, signatures_found):
            if processed % 1000 == 0:
                try:
                    await progress_msg.edit(
                        f"🚀 扫描中... {processed} 条 / 发现 {signatures_found} 重复"
                    )
                except:
                    pass

        results = await session_manager.scan_duplicate_messages(
            event, chat_id=chat_id, progress_callback=progress_callback
        )

        if results:
            total = sum(results.values())
            res_text = "\n".join([f"• {k}: {v}" for k, v in list(results.items())[:10]])
            if len(results) > 10:
                res_text += "\n..."
            await progress_msg.edit(
                f"📊 **扫描完成**\n发现 {total} 条重复:\n{res_text}\n\n请使用 /menu 进行清理"
            )
        else:
            await progress_msg.edit("✨ **扫描完成**\n未发现重复消息")

    except Exception as e:
        logger.error(f"扫描失败: {e}", exc_info=True)
        # 尝试编辑消息，如果失败则发送新消息
        try:
            await progress_msg.edit(f"❌ 扫描失败: {str(e)}")
        except:
            await reply_and_delete(event, f"❌ 扫描失败: {str(e)}")


async def handle_export_keyword_command(event, command):
    """处理 export_keyword 命令 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            return
        rule, source_chat = rule_info
        
    # 使用 Service 层导出关键字
    lines = await rule_management_service.export_keywords(rule.id)
    
    if not lines:
        await reply_and_delete(event, "当前规则没有任何关键字")
        return
    
    # 获取所有关键字并按类型分类
    async with container.db.session() as session:
        from models.models import Keyword
        keywords = (await session.execute(
            select(Keyword).filter_by(rule_id=rule.id)
        )).scalars().all()
        
        normal_lines = []
        regex_lines = []
        for kw in keywords:
            line = f"{kw.keyword} {1 if kw.is_blacklist else 0}"
            if kw.is_regex:
                regex_lines.append(line)
            else:
                normal_lines.append(line)
    
    # 写入并发送
    files_to_send = []
    if normal_lines:
        path = os.path.join(TEMP_DIR, "keywords.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(normal_lines))
        files_to_send.append(path)
    if regex_lines:
        path = os.path.join(TEMP_DIR, "regex_keywords.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(regex_lines))
        files_to_send.append(path)
        
    try:
        if files_to_send:
            await event.client.send_file(event.chat_id, files_to_send)
            await respond_and_delete(event, f"规则: {source_chat.name}")
    finally:
        for f in files_to_send:
            if os.path.exists(f): os.remove(f)


async def handle_export_replace_command(event, client):
    """处理 export_replace 命令 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            return
        rule, source_chat = rule_info

        # 1. 导出数据 (通过 Service)
        lines = await rule_management_service.export_replace_rules(rule.id)
        if not lines:
            await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
            await reply_and_delete(event, "当前规则没有任何替换规则")
            return

        # 2. 写入并发送
        replace_file = os.path.join(TEMP_DIR, 'replace_rules.txt')
        with open(replace_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        try:
            await event.client.send_file(event.chat_id, replace_file)
            await respond_and_delete(event, f"规则: {source_chat.name}")
        finally:
            if os.path.exists(replace_file): os.remove(replace_file)


async def handle_import_command(event, command):
    """处理导入命令 - 使用 RuleManagementService"""
    if not event.message.file:
        await reply_and_delete(event, f"请将文件和 /{command} 命令一起发送")
        return

    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            return
        rule, source_chat = rule_info

        file_path = await event.message.download_media(TEMP_DIR)
        try:
            import aiofiles
            async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
                content = await f.read()
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            
            if command == "import_replace":
                result = await rule_management_service.import_replace_rules(rule.id, lines)
                if result.get('success'):
                    await reply_and_delete(event, f"✅ 成功导入 {result['imported_count']} 条替换规则\n规则: 来自 {source_chat.name}")
                else:
                    await reply_and_delete(event, f"❌ 导入失败: {result.get('error')}")
            else:
                is_regex = command == "import_regex_keyword"
                result = await rule_management_service.import_keywords(rule.id, lines, is_regex)
                if result.get('success'):
                    kw_type = "正则表达式" if is_regex else "关键字"
                    await reply_and_delete(event, f"✅ 成功导入 {result['imported_count']} 个{kw_type}\n跳过重复: {result['duplicate_count']} 个\n规则: 来自 {source_chat.name}")
                else:
                    await reply_and_delete(event, f"❌ 导入失败: {result.get('error')}")
        finally:
            if os.path.exists(file_path): os.remove(file_path)


async def handle_import_excel_command(event):
    """处理 /import_excel 命令 - 使用 RuleManagementService"""
    if not getattr(event.message, "file", None):
        await reply_and_delete(event, "请将 .xlsx 文件与 /import_excel 命令一起发送")
        return

    file_path = await event.message.download_media(TEMP_DIR)
    try:
        import aiofiles
        async with aiofiles.open(file_path, "rb") as f:
            content_bytes = await f.read()

        import asyncio
        from functools import partial
        loop = asyncio.get_running_loop()
        try:
            keywords_rows, replacement_rows = await loop.run_in_executor(
                None, partial(parse_excel, content_bytes)
            )
        except Exception as e:
            await reply_and_delete(event, f"解析Excel失败：{str(e)}")
            return

        result = await rule_management_service.import_excel(keywords_rows, replacement_rows)
        if result.get('success'):
            msg = (
                "✅ 导入完成\n"
                f"关键字：成功 {result['kw_success']} / 跳过或无效 {result['kw_failed']}\n"
                f"替换规则：成功 {result['r_success']} / 跳过或无效 {result['r_failed']}"
            )
            await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
            await reply_and_delete(event, msg)
        else:
            await reply_and_delete(event, f"❌ 导入失败: {result.get('error')}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)


async def handle_ufb_item_change_command(event, command):
    """处理 ufb_item_change 命令"""

    from sqlalchemy import select
    from core.container import container
    # 从container获取数据库会话
    async with container.db.session() as session:
        try:
            rule_info = await _get_current_rule_for_chat(session, event)
            if not rule_info:
                return

            rule, source_chat = rule_info

            # 创建4个按钮
            buttons = [
                [
                    Button.inline("主页关键字", "ufb_item:main"),
                    Button.inline("内容页关键字", "ufb_item:content"),
                ],
                [
                    Button.inline("主页用户名", "ufb_item:main_username"),
                    Button.inline("内容页用户名", "ufb_item:content_username"),
                ],
            ]

            # 发送带按钮的消息
            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(
                event, "请选择要切换的UFB同步配置类型:", buttons=buttons
            )

        except Exception as e:
            await session.rollback()
            logger.error(f"切换UFB配置类型时出错: {str(e)}")
            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(event, "切换UFB配置类型时出错，请检查日志")


async def handle_ufb_bind_command(event, command):
    """处理 ufb_bind 命令 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info

    parts = event.message.text.split()
    if len(parts) < 2:
        await reply_and_delete(event, "用法: /ufb_bind <域名> [类型]")
        return

    domain = parts[1].strip().lower()
    item = parts[2].strip().lower() if len(parts) > 2 else "main"

    valid_items = ["main", "content", "main_username", "content_username"]
    if item not in valid_items:
        await reply_and_delete(
            event, f"类型无效，可选: {', '.join(valid_items)}"
        )
        return

    # 使用 Service 层更新 UFB 设置
    result = await rule_management_service.update_rule(
        rule_id=rule.id,
        ufb_domain=domain,
        ufb_item=item,
        is_ufb=True  # 同时激活 UFB 开关
    )

    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        await reply_and_delete(
            event, f"✅ 已绑定 UFB: {domain} ({item})\n源: {source_chat.name}"
        )
    else:
        await reply_and_delete(event, f"❌ UFB绑定失败: {result.get('error')}")


async def handle_ufb_unbind_command(event, command):
    """处理 ufb_unbind 命令 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        old_domain = rule.ufb_domain

    # 使用 Service 层清除 UFB 设置
    result = await rule_management_service.update_rule(
        rule_id=rule.id,
        ufb_domain=None,
        ufb_item=None,
        is_ufb=False  # 同时关闭 UFB 开关
    )

    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        await reply_and_delete(event, f'✅ 已解绑 UFB: {old_domain or "无"}')
    else:
        await reply_and_delete(event, f"❌ UFB解绑失败: {result.get('error')}")


async def handle_clear_all_keywords_command(event, command):
    """处理 clear_all_keywords 命令 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则。")
            return
        rule, source_chat = rule_info
        
    # 调用服务
    result = await rule_management_service.clear_keywords(rule_id=rule.id)

    if result.get('success'):
        msg = f"✅ {result['message']}\n源聊天: {source_chat.name}"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 清除失败: {result.get('error', '未知错误')}")


async def handle_clear_all_keywords_regex_command(event, command):
    """处理 clear_all_keywords_regex 命令 - 使用 RuleManagementService"""
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则。")
            return
        rule, source_chat = rule_info

    # 调用服务
    result = await rule_management_service.clear_keywords(rule_id=rule.id, is_regex=True)

    if result.get('success'):
        msg = f"✅ {result['message']}\n源聊天: {source_chat.name}"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 清除正则关键字失败: {result.get('error', '未知错误')}")


async def handle_clear_all_replace_command(event, command):
    """处理 clear_all_replace 命令 - 使用 RuleManagementService"""
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则。")
            return
        rule, _ = rule_info

    # 调用服务
    result = await rule_management_service.clear_replace_rules(rule_id=rule.id)

    if result.get('success'):
        msg = f"✅ {result['message']}\n已自动关闭该规则的替换模式"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 清除失败: {result.get('error', '未知错误')}")


async def handle_copy_keywords_command(event, command):
    """处理 copy_keywords 和 copy_keywords_regex 命令 - 异步重构版"""
    is_regex_cmd = command == "copy_keywords_regex"
    parts = event.message.text.split()

    if len(parts) != 2:
        await reply_and_delete(event, f"用法: /{command} <源规则ID>")
        return

    try:
        source_rule_id = int(parts[1])
    except ValueError:
        await reply_and_delete(event, "规则ID必须是数字")
        return

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from models.models import ForwardRule
    
    # 从container获取数据库会话
    async with container.db.session() as session:
        try:
            # 1. 获取目标规则 (含 keywords)
            rule_info = await _get_current_rule_for_chat(session, event)
            if not rule_info:
                return
            target_rule_base, _ = rule_info

            # 重新加载目标规则的关键字
            stmt_target = (
                select(ForwardRule)
                .where(ForwardRule.id == target_rule_base.id)
                .options(selectinload(ForwardRule.keywords))
            )
            target_rule = (await session.execute(stmt_target)).scalar_one()

            # 2. 获取源规则 (含 keywords)
            stmt_source = (
                select(ForwardRule)
                .where(ForwardRule.id == source_rule_id)
                .options(selectinload(ForwardRule.keywords))
            )
            source_rule = (await session.execute(stmt_source)).scalar_one_or_none()

            if not source_rule:
                await reply_and_delete(event, f"找不到规则ID: {source_rule_id}")
                return

            success_count = 0
            skip_count = 0

            # 缓存目标规则已有的关键字
            # 注意：这里区分正则和普通
            existing = {
                (k.keyword, k.is_blacklist)
                for k in target_rule.keywords
                if k.is_regex == is_regex_cmd
            }

            for kw in source_rule.keywords:
                # 只处理符合当前命令类型的关键字 (正则或非正则)
                if kw.is_regex == is_regex_cmd:
                    key = (kw.keyword, kw.is_blacklist)
                    if key not in existing:
                        session.add(
                            Keyword(
                                rule_id=target_rule.id,
                                keyword=kw.keyword,
                                is_regex=is_regex_cmd,
                                is_blacklist=kw.is_blacklist,
                            )
                        )
                        existing.add(key)
                        success_count += 1
                    else:
                        skip_count += 1

            await session.commit()

            type_str = "正则关键字" if is_regex_cmd else "关键字"
            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(
                event,
                f"✅ 已从规则 `{source_rule_id}` 复制{type_str}到当前规则\n"
                f"成功: {success_count} 个\n"
                f"跳过: {skip_count} 个",
                parse_mode="markdown",
            )

        except Exception as e:
            await session.rollback()
            logger.error(f"复制关键字出错: {str(e)}")
            await reply_and_delete(event, "复制关键字时出错")


async def handle_copy_keywords_regex_command(event, command):
    """处理复制正则关键字命令 - 调用通用处理函数"""
    await handle_copy_keywords_command(event, command)


async def handle_copy_replace_command(event, command):
    """处理复制替换规则命令 - 异步重构版"""
    parts = event.message.text.split()
    if len(parts) != 2:
        await reply_and_delete(event, "用法: /copy_replace <规则ID>")
        return

    try:
        source_rule_id = int(parts[1])
    except ValueError:
        await reply_and_delete(event, "规则ID必须是数字")
        return

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from sqlalchemy import select
    from models.models import ForwardRule
    
    # 从container获取数据库会话
    async with container.db.session() as session:
        try:
            # 1. 获取目标规则 (含 replace_rules)
            rule_info = await _get_current_rule_for_chat(session, event)
            if not rule_info:
                return
            target_rule_base, _ = rule_info

            # 重新加载目标规则的替换规则
            stmt_target = (
                select(ForwardRule)
                .where(ForwardRule.id == target_rule_base.id)
                .options(selectinload(ForwardRule.replace_rules))
            )
            target_rule = (await session.execute(stmt_target)).scalar_one()

            # 2. 获取源规则 (含 replace_rules)
            stmt_source = (
                select(ForwardRule)
                .where(ForwardRule.id == source_rule_id)
                .options(selectinload(ForwardRule.replace_rules))
            )
            source_rule = (await session.execute(stmt_source)).scalar_one_or_none()

            if not source_rule:
                await reply_and_delete(event, f"找不到规则ID: {source_rule_id}")
                return

            # 复制替换规则
            success_count = 0
            skip_count = 0

            # 缓存目标规则已有的替换规则
            existing_replaces = {
                (r.pattern, r.content) for r in target_rule.replace_rules
            }
            for replace_rule in source_rule.replace_rules:
                key = (replace_rule.pattern, replace_rule.content)
                if key not in existing_replaces:
                    new_rule = ReplaceRule(
                        rule_id=target_rule.id,
                        pattern=replace_rule.pattern,
                        content=replace_rule.content,
                    )
                    session.add(new_rule)
                    existing_replaces.add(key)
                    success_count += 1
                else:
                    skip_count += 1

            await session.commit()

            # 确保启用替换模式
            if success_count > 0:
                await async_delete_user_message(
                    event.client, event.message.chat_id, event.message.id, 0
                )
            await reply_and_delete(
                event,
                f"✅ 已从规则 `{source_rule_id}` 复制替换规则到规则 `{target_rule.id}`\n"
                f"成功复制: {success_count} 个\n"
                f"跳过重复: {skip_count} 个\n",
                parse_mode="markdown",
            )

        except Exception as e:
            await session.rollback()
            logger.error(f"复制替换规则时出错: {str(e)}")
            await reply_and_delete(event, "复制替换规则时出错，请检查日志")


async def handle_copy_rule_command(event, command):
    """处理复制规则命令 - 异步重构版 (使用 RuleManagementService)"""
    parts = event.message.text.split()

    if len(parts) not in [2, 3]:
        await reply_and_delete(event, "用法: /copy_rule <源规则ID> [目标规则ID]")
        return

    try:
        source_rule_id = int(parts[1])
        target_rule_id = int(parts[2]) if len(parts) == 3 else None
    except ValueError:
        await reply_and_delete(event, "规则ID必须是数字")
        return

    try:
        # 调用 RuleManagementService.copy_rule 方法
        result = await container.rule_management_service.copy_rule(source_rule_id, target_rule_id)
        
        if result.get('success'):
            await reply_and_delete(event, f"规则复制成功！新规则ID: {result.get('new_rule_id')}")
        else:
            await reply_and_delete(event, f"规则复制失败: {result.get('error')}")
    except Exception as e:
        logger.error(f"复制规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "复制规则时出错，请检查日志")


async def handle_remove_all_keyword_command(event, command, parts):
    """处理 remove_all_keyword 命令 - 异步重构版"""
    message_text = event.message.text
    if len(message_text.split(None, 1)) < 2:
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, f"用法: /{command} <关键字1> [关键字2] ...")
        return

    _, args_text = message_text.split(None, 1)
    try:
        keywords = shlex.split(args_text)
    except ValueError:
        await reply_and_delete(event, "参数格式错误：请确保引号正确配对")
        return

    if not keywords:
        await reply_and_delete(event, "请提供至少一个关键字")
        return

    # 调用服务
    result = await rule_management_service.delete_keywords_all_rules(keywords=keywords)

    if result.get('success'):
        msg = f"✅ {result['message']}"
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 批量删除失败: {result.get('error', '未知错误')}")


async def handle_add_all_command(event, command, parts):
    """处理 add_all 和 add_regex_all 命令 - 异步重构版"""
    message_text = event.message.text
    if len(message_text.split(None, 1)) < 2:
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, f"用法: /{command} <关键字1> [关键字2] ...")
        return

    _, args_text = message_text.split(None, 1)
    is_regex = (command == "add_regex_all")

    try:
        if not is_regex:
            keywords = shlex.split(args_text)
        else:
            keywords = args_text.split() if len(args_text.split()) > 0 else [args_text]
    except ValueError:
        await reply_and_delete(event, "参数格式错误：请确保引号正确配对")
        return

    if not keywords:
        await reply_and_delete(event, "请提供至少一个关键字")
        return

    # 获取当前规则以确定 AddMode (黑/白名单)
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 当前频道未绑定任何规则，无法确定添加模式。")
            return
        
        current_rule, _ = rule_info
        is_blacklist = current_rule.add_mode == AddMode.BLACKLIST

    # 调用服务执行批量添加
    result = await rule_management_service.add_keywords_all_rules(
        keywords=keywords,
        is_regex=is_regex,
        is_blacklist=is_blacklist
    )

    if result.get('success'):
        keyword_type = "正则表达式" if is_regex else "关键字"
        keywords_text = "\n".join(f"- {k}" for k in keywords)
        msg = f"✅ {result['message']}\n类型: {keyword_type}\n同步规则数: {result.get('rule_count', 0)}\n列表:\n{keywords_text}"
        
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 批量添加失败: {result.get('error', '未知错误')}")


async def handle_replace_all_command(event, parts):
    """处理 replace_all 命令 - 异步重构版"""
    message_text = event.message.text
    if len(message_text.split(None, 1)) < 2:
        await reply_and_delete(event, "用法: /replace_all <匹配规则> [替换内容]")
        return

    _, args_text = message_text.split(None, 1)
    # 简单解析 pattern 和 content
    args_parts = args_text.split(None, 1)
    pattern = args_parts[0]
    content = args_parts[1] if len(args_parts) > 1 else ""

    # 调用服务
    result = await rule_management_service.add_replace_rules_all_rules(
        patterns=[pattern],
        replacements=[content],
        is_regex=True # replace_all 默认通常是正则，或者根据具体逻辑确定
    )

    if result.get('success'):
        action_type = "删除" if not content else "替换"
        msg = f"✅ {result['message']}\n匹配模式: {pattern}\n动作: {action_type}"
        if content:
            msg += f"\n替换为: {content}"
        
        await async_delete_user_message(event.client, event.message.chat_id, event.message.id, 0)
        await reply_and_delete(event, msg)
    else:
        await reply_and_delete(event, f"❌ 批量添加失败: {result.get('error', '未知错误')}")


async def handle_list_rule_command(event, command, parts):
    """处理 list_rule 命令 - 异步分页重构版"""
    try:
        # 解析页码
        try:
            page = int(parts[1]) if len(parts) > 1 else 1
            if page < 1:
                page = 1
        except ValueError:
            await reply_and_delete(event, "页码必须是数字")
            return

        per_page = 30

        # ✅ 使用 Repository 获取数据，而不是自己写 SQL
        rules, total_rules = await container.rule_repo.get_all(page, per_page)

        if not rules:
            await reply_and_delete(event, "当前没有任何转发规则")
            return

        total_pages = (total_rules + per_page - 1) // per_page
        if page > total_pages:
            page = total_pages
            rules, total_rules = await container.rule_repo.get_all(page, per_page)

            # 3. 构建消息
            message_parts = [f"📋 转发规则列表 (第{page}/{total_pages}页)：\n"]

            for rule in rules:
                # 因为使用了 selectinload，这里访问 source_chat 不会阻塞或报错
                source_name = rule.source_chat.name if rule.source_chat else "Unknown"
                source_tid = (
                    rule.source_chat.telegram_chat_id if rule.source_chat else "N/A"
                )
                target_name = rule.target_chat.name if rule.target_chat else "Unknown"
                target_tid = (
                    rule.target_chat.telegram_chat_id if rule.target_chat else "N/A"
                )

                rule_desc = (
                    f"<b>ID: {rule.id}</b>\n"
                    f"<blockquote>来源: {source_name} ({source_tid})\n"
                    f"目标: {target_name} ({target_tid})\n"
                    "</blockquote>"
                )
                message_parts.append(rule_desc)

            # 4. 构建按钮
            buttons = []
            nav_row = []
            if page > 1:
                nav_row.append(Button.inline("⬅️ 上一页", f"page_rule:{page-1}"))
            else:
                nav_row.append(Button.inline("⬅️", "noop"))
            nav_row.append(Button.inline(f"{page}/{total_pages}", "noop"))
            if page < total_pages:
                nav_row.append(Button.inline("下一页 ➡️", f"page_rule:{page+1}"))
            else:
                nav_row.append(Button.inline("➡️", "noop"))
            buttons.append(nav_row)

            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(
                event, "\n".join(message_parts), buttons=buttons, parse_mode="html"
            )

    except Exception as e:
        logger.error(f"列出规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "获取规则列表时发生错误，请检查日志")


async def handle_delete_rule_command(event, command, parts):
    """处理 delete_rule 命令 - 异步重构版"""
    if len(parts) < 2:
        await reply_and_delete(event, f"用法: /{command} <ID1> [ID2] ...")
        return

    try:
        ids_to_remove = [int(x) for x in parts[1:]]
    except ValueError:
        await reply_and_delete(event, "ID必须是数字")
        return

    try:
        success_ids = []
        failed_ids = []
        not_found_ids = []

        for rule_id in ids_to_remove:
            # ✅ 使用 Service 删除规则
            result = await container.rule_management_service.delete_rule(rule_id)

            if result["success"]:
                success_ids.append(rule_id)

                # 异步 RSS 删除调用 (保持非阻塞)
                # 将 HTTP 请求放入后台任务，或在此处异步等待
                try:
                    import aiohttp

                    rss_url = f"http://{RSS_HOST}:{RSS_PORT}/api/rule/{rule_id}"
                    # 使用极短超时，避免阻塞删除流程
                    timeout = aiohttp.ClientTimeout(total=2)
                    async with aiohttp.ClientSession(timeout=timeout) as client_session:
                        async with client_session.delete(rss_url) as response:
                            if response.status != 200:
                                logger.warning(f"RSS同步删除失败: {response.status}")
                except ImportError:
                    pass
                except Exception as rss_e:
                    logger.warning(f"RSS同步删除出错: {rss_e}")
            else:
                if "error" in result and "规则不存在" in result["error"]:
                    not_found_ids.append(rule_id)
                else:
                    failed_ids.append(rule_id)

        # 构建响应消息
        response_parts = []
        if success_ids:
            response_parts.append(f'✅ 成功删除: {", ".join(map(str, success_ids))}')
        if not_found_ids:
            response_parts.append(f'❓ 未找到: {", ".join(map(str, not_found_ids))}')
        if failed_ids:
            response_parts.append(f'❌ 删除失败: {", ".join(map(str, failed_ids))}')

        await async_delete_user_message(
            event.client, event.message.chat_id, event.message.id, 0
        )
        await reply_and_delete(event, "\n".join(response_parts) or "没有规则被删除")

    except Exception as e:
        logger.error(f"删除规则时发生致命错误: {str(e)}")
        await reply_and_delete(event, "删除规则时发生错误，请检查日志")


async def handle_delete_rss_user_command(event, command, parts):
    """处理 delete_rss_user 命令 - 异步重构版"""
    from models.models import User
    from sqlalchemy import select
    
    # 从container获取数据库会话
    async with container.db.session() as session:
        try:
            specified_username = parts[1].strip() if len(parts) > 1 else None

            # 异步查询所有用户
            stmt = select(User)
            result = await session.execute(stmt)
            users = result.scalars().all()

            if not users:
                await reply_and_delete(event, "RSS系统中没有用户账户")
                return

            # 指定用户名删除
            if specified_username:
                stmt_user = select(User).filter(User.username == specified_username)
                user = (await session.execute(stmt_user)).scalar_one_or_none()

                if user:
                    await session.delete(user)
                    await session.commit()
                    await reply_and_delete(
                        event, f"已删除RSS用户: {specified_username}"
                    )
                else:
                    await reply_and_delete(
                        event, f"未找到用户名为 '{specified_username}' 的RSS用户"
                    )
                return

            # 未指定且只有一个用户
            if len(users) == 1:
                user = users[0]
                username = user.username
                await session.delete(user)
                await session.commit()
                await reply_and_delete(event, f"已删除RSS用户: {username}")
                return

            # 多个用户列表展示
            usernames = [u.username for u in users]
            user_list = "\n".join(
                [f"{i+1}. {name}" for i, name in enumerate(usernames)]
            )
            await reply_and_delete(
                event,
                f"请指定要删除的用户名:\n/delete_rss_user <用户名>\n\n现有用户:\n{user_list}",
            )

        except Exception as e:
            await session.rollback()
            logger.error(f"删除RSS用户出错: {str(e)}", exc_info=True)
            await reply_and_delete(event, f"操作失败: {str(e)}")


async def handle_db_info_command(event):
    """处理数据库信息命令 - 异步非阻塞版"""
    try:
        import asyncio

        from models.models import get_database_info

        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, get_database_info)

        if info:
            response = (
                "📊 **数据库详情**\n\n"
                f"📁 纯数据: {info['db_size']:,} B\n"
                f"📝 WAL日志: {info['wal_size']:,} B\n"
                f"💾 总占用: {info['total_size']/1024/1024:.2f} MB\n"
                f"🗂️ 表总数: {info['table_count']}\n"
                f"📈 索引数: {info['index_count']}"
            )
        else:
            response = "❌ 无法获取信息"

        await reply_and_delete(event, response, delete_after_seconds=30)
    except Exception as e:
        await reply_and_delete(event, f"获取失败: {str(e)}", delete_after_seconds=10)


async def handle_db_backup_command(event):
    """处理数据库备份命令 - 异步非阻塞版"""
    try:
        from datetime import datetime
        from functools import partial

        import asyncio

        from models.models import backup_database

        progress_msg = await event.reply("🔄 正在备份数据库 (后台进行中)...")

        # 获取当前事件循环
        loop = asyncio.get_running_loop()

        # 在线程池中执行同步的备份函数
        # backup_database 是阻塞函数，必须 await run_in_executor
        backup_path = await loop.run_in_executor(None, backup_database)

        if backup_path:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            response = (
                "✅ **数据库备份成功**\n\n"
                f"📁 备份文件: `{backup_path}`\n"
                f"⏰ 备份时间: {timestamp}"
            )
        else:
            response = "❌ 数据库备份失败"

        await progress_msg.edit(response)
        await asyncio.sleep(20)
        await progress_msg.delete()
    except Exception as e:
        await reply_and_delete(
            event, f"数据库备份失败: {str(e)}", delete_after_seconds=10
        )


async def handle_db_optimize_command(event):
    """处理数据库优化命令 - 使用 SystemService 统一逻辑"""
    try:
        from services.system_service import system_service
        
        progress_msg = await event.reply("🔧 正在进行深度数据库优化 (清理碎片+分析统计)...")
        
        # 调用统一服务执行深度优化
        result = await system_service.run_db_optimization(deep=True)
        
        if result.get("success"):
            response = (
                "✅ **数据库优化完成**\n\n"
                f"⏱️ 耗时: {result.get('duration')}s\n"
                f"🧹 碎片清理: ✅ (VACUUM)\n"
                f"📊 统计分析: ✅ (ANALYZE)\n"
                f"🗑️ 日志清理: {result.get('deleted_logs', 0)} 条记录"
            )
        else:
            response = f"❌ 数据库优化失败: {result.get('error')}"

        await progress_msg.edit(response)
        await asyncio.sleep(20)
        await progress_msg.delete()
    except Exception as e:
        logger.error(f"数据库优化指令执行失败: {e}", exc_info=True)
        await reply_and_delete(
            event, f"数据库优化失败: {str(e)}", delete_after_seconds=10
        )


async def handle_db_health_command(event):
    """处理数据库健康检查 - 异步非阻塞版"""
    try:
        import asyncio

        from models.models import get_db_health

        loop = asyncio.get_running_loop()
        health = await loop.run_in_executor(None, get_db_health)

        if health["status"] == "healthy":
            response = "💚 **数据库健康**\n✅ 连接/读写/会话均正常"
        else:
            response = f"❤️ **数据库异常**\n❌ {health.get('error', '未知错误')}"

        await reply_and_delete(event, response, delete_after_seconds=20)
    except Exception as e:
        await reply_and_delete(event, "检查失败", delete_after_seconds=10)


async def handle_video_cache_stats_command(event):
    """查看视频哈希缓存统计"""
    try:
        from utils.db.persistent_cache import get_persistent_cache

        # 假设 cache 操作足够快，不做线程池封装，但添加异常捕获
        pc = get_persistent_cache()
        stats = pc.stat_prefix("video:hash:")

        count = stats.get("count", 0)
        size_str = ""
        if stats.get("bytes") is not None:
            size_str = f", ~{stats.get('bytes')/1024:.1f} KB"

        await reply_and_delete(
            event,
            f"🎞️ 视频缓存 (partial_md5)\n数量: {count} keys{size_str}",
            delete_after_seconds=20,
        )
    except Exception as e:
        await reply_and_delete(
            event, f"获取统计失败: {str(e)}", delete_after_seconds=10
        )


async def handle_video_cache_clear_command(event, parts):
    """清理视频哈希缓存：/video_cache_clear [partial_md5]"""
    try:
        algo = (parts[1] if len(parts) > 1 else "partial_md5").strip().lower()
        if algo not in {"partial_md5"}:
            await reply_and_delete(
                event, "不支持的算法，仅支持 partial_md5", delete_after_seconds=10
            )
            return
        from utils.db.persistent_cache import get_persistent_cache

        pc = get_persistent_cache()
        deleted = pc.delete_prefix("video:hash:")
        await reply_and_delete(
            event,
            f"✅ 已清理视频哈希缓存（{algo}）：{deleted} 条",
            delete_after_seconds=10,
        )
    except Exception as e:
        await reply_and_delete(event, f"清理失败: {str(e)}", delete_after_seconds=10)


async def handle_system_status_command(event):
    """处理系统状态命令 - 异步非阻塞版"""
    try:
        from datetime import datetime
        from functools import partial

        import asyncio
        import time

        from models.models import get_database_info, get_db_health

        loop = asyncio.get_running_loop()

        # 1. 在后台线程获取系统信息 (psutil 可能慢)
        def get_sys_info():
            try:
                import psutil

                return {
                    "cpu": psutil.cpu_percent(interval=None),  # 非阻塞模式
                    "mem": psutil.virtual_memory(),
                    "disk": psutil.disk_usage("./"),
                    "avail": True,
                }
            except ImportError:
                return {"avail": False}

        sys_info = await loop.run_in_executor(None, get_sys_info)

        # 2. 在后台线程获取数据库信息
        db_info = await loop.run_in_executor(None, get_database_info)
        db_health = await loop.run_in_executor(None, get_db_health)

        # 计算运行时间
        start_time = getattr(handle_system_status_command, "start_time", time.time())
        if not hasattr(handle_system_status_command, "start_time"):
            handle_system_status_command.start_time = start_time
        uptime = time.time() - start_time
        uptime_str = f"{int(uptime//3600)}h {int((uptime%3600)//60)}m {int(uptime%60)}s"

        # 构建响应
        response_parts = ["🖥️ **系统状态报告**\n"]

        if sys_info["avail"]:
            mem = sys_info["mem"]
            disk = sys_info["disk"]
            response_parts.extend(
                [
                    "**💻 系统资源**\n",
                    f"🔥 CPU 使用率: {sys_info['cpu']}%\n",
                    f"💾 内存使用: {mem.percent}% ({mem.used/1024/1024/1024:.1f}GB/{mem.total/1024/1024/1024:.1f}GB)\n",
                    f"💿 磁盘使用: {disk.percent}% ({disk.used/1024/1024/1024:.1f}GB/{disk.total/1024/1024/1024:.1f}GB)\n\n",
                ]
            )
        else:
            response_parts.append("⚠️ 系统监控不可用 (需安装 psutil)\n\n")

        response_parts.append("**🗄️ 数据库状态**\n")
        status_icon = "💚" if db_health["status"] == "healthy" else "❤️"
        response_parts.append(f"{status_icon} 健康状态: {db_health['status']}\n")

        if db_info:
            response_parts.extend(
                [
                    f"📊 大小: {db_info['total_size']/1024/1024:.2f} MB\n",
                    f"🗂️ 表: {db_info['table_count']} | 📈 索引: {db_info['index_count']}\n\n",
                ]
            )

        response_parts.extend(
            [
                "**⏰ 运行信息**\n",
                f"🚀 运行时间: {uptime_str}\n",
                f"📅 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ]
        )

        await reply_and_delete(event, "".join(response_parts), delete_after_seconds=60)

    except Exception as e:
        logger.error(f"系统状态获取失败: {e}", exc_info=True)
        await reply_and_delete(event, "获取系统状态失败", delete_after_seconds=10)


async def handle_admin_panel_command(event):
    """处理管理面板命令"""
    try:
        from telethon import Button

        buttons = [
            [
                Button.inline("📊 数据库信息", "admin_db_info"),
                Button.inline("💚 健康检查", "admin_db_health"),
            ],
            [
                Button.inline("💾 备份数据库", "admin_db_backup"),
                Button.inline("🔧 优化数据库", "admin_db_optimize"),
            ],
            [
                Button.inline("🖥️ 系统状态", "admin_system_status"),
                Button.inline("📋 运行日志", "admin_logs"),
            ],
            [
                Button.inline("🗑️ 清理维护", "admin_cleanup_menu"),
                Button.inline("📈 统计报告", "admin_stats"),
            ],
            [
                Button.inline("⚙️ 系统配置", "admin_config"),
                Button.inline("🔄 重启服务", "admin_restart"),
            ],
            [Button.inline("❌ 关闭面板", "close_admin_panel")],
        ]

        response = "🔧 **系统管理面板**\n\n" "选择需要执行的管理操作："

        await event.reply(response, buttons=buttons)
    except Exception as e:
        await reply_and_delete(
            event, f"管理面板加载失败: {str(e)}", delete_after_seconds=10
        )


async def handle_forward_stats_command(event, command):
    """处理转发统计命令"""
    try:
        from datetime import datetime

        # 解析参数
        parts = command.strip().split()
        date = None
        chat_id = None

        if len(parts) > 1:
            if parts[1].isdigit() or parts[1].startswith("-"):
                # 参数是聊天ID
                chat_id = int(parts[1])
            else:
                # 参数是日期
                date = parts[1]

        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # 获取统计数据
        summary = await forward_recorder.get_daily_summary(date)

        # 构建统计文本
        if summary.get("total_forwards", 0) == 0:
            text = f"📊 **转发统计 - {date}**\n\n❌ 当日无转发记录"
        else:
            text = f"📊 **转发统计 - {date}**\n\n"
            text += f"📈 总转发数: {summary.get('total_forwards', 0)}\n"
            text += f"💾 总大小: {summary.get('total_size_bytes', 0) / 1024 / 1024:.2f} MB\n"
            text += (
                f"⏱️ 总时长: {summary.get('total_duration_seconds', 0) // 60} 分钟\n\n"
            )

            # 按类型统计
            types = summary.get("types", {})
            if types:
                text += "📱 **按类型统计:**\n"
                for msg_type, count in sorted(
                    types.items(), key=lambda x: x[1], reverse=True
                ):
                    text += f"  • {msg_type}: {count}\n"
                text += "\n"

            # 按聊天统计 (显示前5个)
            chats = summary.get("chats", {})
            if chats:
                text += "💬 **活跃聊天 (前5):**\n"
                for chat, count in sorted(
                    chats.items(), key=lambda x: x[1], reverse=True
                )[:5]:
                    text += f"  • 聊天{chat}: {count}\n"
                text += "\n"

            # 按规则统计 (显示前5个)
            rules = summary.get("rules", {})
            if rules:
                text += "⚙️ **活跃规则 (前5):**\n"
                for rule, count in sorted(
                    rules.items(), key=lambda x: x[1], reverse=True
                )[:5]:
                    text += f"  • 规则{rule}: {count}\n"

        await respond_and_delete(event, text, delete_delay=15)

    except Exception as e:
        logger.error(f"获取转发统计失败: {e}")
        await respond_and_delete(event, f"❌ 获取统计失败: {str(e)}", delete_delay=5)


async def handle_forward_search_command(event, command):
    """处理转发记录搜索命令"""
    try:
        # 解析参数
        parts = command.strip().split()

        kwargs = {"limit": 10}

        if len(parts) > 1:
            for i in range(1, len(parts)):
                part = parts[i]
                if part.startswith("chat:"):
                    kwargs["chat_id"] = int(part[5:])
                elif part.startswith("user:"):
                    kwargs["user_id"] = int(part[5:])
                elif part.startswith("type:"):
                    kwargs["message_type"] = part[5:]
                elif part.startswith("rule:"):
                    kwargs["rule_id"] = int(part[5:])
                elif part.startswith("date:"):
                    kwargs["start_date"] = part[5:]
                    kwargs["end_date"] = part[5:]
                elif part.startswith("limit:"):
                    kwargs["limit"] = min(20, int(part[6:]))

        # 搜索记录
        records = await forward_recorder.search_records(**kwargs)

        if not records:
            text = "🔍 **转发记录搜索**\n\n❌ 未找到匹配记录"
        else:
            text = f"🔍 **转发记录搜索** (找到 {len(records)} 条)\n\n"

            for i, record in enumerate(records[:10], 1):
                msg_info = record.get("message_info", {})
                chat_info = record.get("chat_info", {})
                forward_info = record.get("forward_info", {})

                timestamp = record.get("timestamp", "")[:19].replace("T", " ")
                msg_type = msg_info.get("type", "unknown")
                source_id = chat_info.get("source_chat_id", 0)
                target_id = chat_info.get("target_chat_id", 0)
                forward_type = forward_info.get("type", "unknown")
                size = msg_info.get("size_bytes", 0)

                text += f"**{i}.** `{timestamp}`\n"
                text += f"   类型: {msg_type} | 大小: {size//1024}KB\n"
                text += f"   {source_id} → {target_id} ({forward_type})\n"

                if msg_info.get("text"):
                    preview = msg_info["text"][:50]
                    text += f"   内容: {preview}{'...' if len(msg_info['text']) > 50 else ''}\n"

                text += "\n"

        await respond_and_delete(event, text, delete_delay=20)

    except Exception as e:
        logger.error(f"搜索转发记录失败: {e}")
        await respond_and_delete(event, f"❌ 搜索失败: {str(e)}", delete_delay=5)


# =============== 增强搜索功能 ===============


async def handle_search_bound_command(event, command, parts):
    """搜索已绑定的群组 - 使用增强搜索系统"""
    try:
        # 获取搜索关键词
        search_query = " ".join(parts[1:]).strip() if len(parts) > 1 else ""

        if not search_query:
            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(
                event,
                "请提供搜索关键词，用法: /search_bound <关键词>\n或使用 /search 进入完整搜索界面",
            )
            return

        # 使用增强搜索系统
        from handlers.search_ui_manager import SearchUIManager
        from utils.helpers.common import get_user_client
        from utils.helpers.search_system import SearchFilter, SearchType, get_search_system

        # 创建筛选器，只搜索已绑定群组
        filters = SearchFilter(search_type=SearchType.BOUND_CHATS)

        # 执行搜索（正确获取异步客户端）
        user_client = await get_user_client()
        search_system = get_search_system(user_client)
        response = await search_system.search(search_query, filters, 1)

        # 生成搜索结果界面
        message_text = SearchUIManager.generate_search_message(response)
        buttons = SearchUIManager.generate_pagination_buttons(response, "search")

        await async_delete_user_message(
            event.client, event.message.chat_id, event.message.id, 0
        )
        await event.reply(message_text, buttons=buttons, parse_mode="HTML")

    except Exception as e:
        logger.error(f"搜索已绑定群组时发生错误: {str(e)}")
        await async_delete_user_message(
            event.client, event.message.chat_id, event.message.id, 0
        )
        await reply_and_delete(event, f"搜索失败: {str(e)}")


async def handle_search_public_command(event, command, parts):
    """搜索Telegram公开群组 - 使用增强搜索系统"""
    try:
        # 获取搜索关键词
        search_query = " ".join(parts[1:]).strip() if len(parts) > 1 else ""

        if not search_query:
            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(
                event,
                "请提供搜索关键词，用法: /search_public <关键词>\n或使用 /search 进入完整搜索界面",
            )
            return

        # 发送搜索进度消息
        progress_msg = await event.reply("🔍 正在搜索公开群组，请稍候...")

        try:
            # 使用增强搜索系统
            from handlers.search_ui_manager import SearchUIManager
            from utils.helpers.common import get_user_client
            from utils.helpers.search_system import SearchFilter, SearchType, get_search_system

            # 创建筛选器，只搜索公开群组
            filters = SearchFilter(search_type=SearchType.PUBLIC_CHATS)

            # 执行搜索（正确获取异步客户端）
            user_client = await get_user_client()
            search_system = get_search_system(user_client)
            response = await search_system.search(search_query, filters, 1)

            # 生成搜索结果界面
            message_text = SearchUIManager.generate_search_message(response)
            buttons = SearchUIManager.generate_pagination_buttons(response, "search")

            await progress_msg.edit(message_text, buttons=buttons, parse_mode="HTML")

        except Exception as search_error:
            logger.error(f"搜索公开群组时发生错误: {str(search_error)}")
            await progress_msg.edit(f"搜索失败: {str(search_error)}")

    except Exception as e:
        logger.error(f"处理搜索公开群组命令时发生错误: {str(e)}")
        await async_delete_user_message(
            event.client, event.message.chat_id, event.message.id, 0
        )
        await reply_and_delete(event, f"命令处理失败: {str(e)}")


async def handle_search_all_command(event, command, parts):
    """搜索所有群组（已绑定+公开）- 使用增强搜索系统"""
    try:
        # 获取搜索关键词
        search_query = " ".join(parts[1:]).strip() if len(parts) > 1 else ""

        if not search_query:
            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(
                event,
                "请提供搜索关键词，用法: /search_all <关键词>\n或使用 /search 进入完整搜索界面",
            )
            return

        # 发送搜索进度消息
        progress_msg = await event.reply("🔍 正在搜索所有群组，请稍候...")

        try:
            # 使用增强搜索系统
            from handlers.search_ui_manager import SearchUIManager
            from utils.helpers.common import get_user_client
            from utils.helpers.search_system import SearchFilter, SearchType, get_search_system

            # 创建筛选器，搜索所有类型
            filters = SearchFilter(search_type=SearchType.ALL)

            # 执行搜索（正确获取异步客户端）
            user_client = await get_user_client()
            search_system = get_search_system(user_client)
            response = await search_system.search(search_query, filters, 1)

            # 生成搜索结果界面
            message_text = SearchUIManager.generate_search_message(response)
            buttons = SearchUIManager.generate_pagination_buttons(response, "search")

            await progress_msg.edit(message_text, buttons=buttons, parse_mode="HTML")

        except Exception as search_error:
            logger.error(f"综合搜索时发生错误: {str(search_error)}")
            await progress_msg.edit(f"搜索失败: {str(search_error)}")

    except Exception as e:
        logger.error(f"处理综合搜索命令时发生错误: {str(e)}")
        try:
            await progress_msg.edit(f"搜索失败: {str(e)}")
        except:
            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await reply_and_delete(event, f"搜索失败: {str(e)}")


async def handle_search_command(event, command, parts):
    """增强搜索命令 - 主入口"""
    try:
        # 如果有搜索关键词，直接执行搜索
        if len(parts) > 1:
            search_query = " ".join(parts[1:]).strip()

            # 发送搜索进度消息
            progress_msg = await event.reply("🔍 正在搜索，请稍候...")

            # 使用增强搜索系统
            from handlers.search_ui_manager import SearchUIManager
            from utils.helpers.common import get_user_client
            from utils.helpers.search_system import SearchFilter, get_search_system

            # 执行搜索（正确获取异步客户端）
            user_client = await get_user_client()
            search_system = get_search_system(user_client)
            response = await search_system.search(search_query, SearchFilter(), 1)

            # 生成搜索结果界面
            message_text = SearchUIManager.generate_search_message(response)
            buttons = SearchUIManager.generate_pagination_buttons(response, "search")

            await progress_msg.edit(message_text, buttons=buttons, parse_mode="HTML")
        else:
            # 显示搜索帮助界面
            message_text = (
                "🔍 <b>增强搜索系统</b>\n\n"
                "🎯 <b>快速搜索命令：</b>\n"
                "• <code>/search &lt;关键词&gt;</code> - 智能搜索\n"
                "• <code>/search_bound &lt;关键词&gt;</code> - 搜索已绑定群组\n"
                "• <code>/search_public &lt;关键词&gt;</code> - 搜索公开群组\n"
                "• <code>/search_all &lt;关键词&gt;</code> - 搜索所有群组\n\n"
                "✨ <b>功能特点：</b>\n"
                "• 📊 分页浏览结果\n"
                "• 🎛️ 类型筛选（频道/群组/消息等）\n"
                "• 🔄 多种排序方式（时间/大小/热度）\n"
                "• 📦 智能缓存（24小时）\n"
                "• 🎯 精确匹配和模糊搜索\n\n"
                "💡 <b>使用提示：</b>\n"
                "直接发送关键词或使用上方命令开始搜索"
            )

            await async_delete_user_message(
                event.client, event.message.chat_id, event.message.id, 0
            )
            await event.reply(message_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"处理搜索命令时发生错误: {str(e)}")
        await async_delete_user_message(
            event.client, event.message.chat_id, event.message.id, 0
        )
        await reply_and_delete(event, f"搜索命令处理失败: {str(e)}")


async def handle_logs_command(event, parts):
    """处理 /logs [lines] [error]"""
    lines = 50
    log_type = "app"
    try:
        if len(parts) > 1:
            for part in parts[1:]:
                if part.isdigit():
                    lines = int(part)
                elif part.lower() == "error":
                    log_type = "error"
    except Exception:
        pass
        
    from services.system_service import system_service
    content = system_service.get_logs(lines, log_type=log_type)
    if not content.strip():
        msg = f"📝 **{log_type.upper()} Log (Last {lines} lines):**\n\n(Empty)"
    else:
        # Avoid Telegram Message Limit (4096 chars)
        if len(content) > 3000:
            content = content[-3000:]
            content = f"...(truncated)...\n{content}"
        msg = f"📝 **{log_type.upper()} Log (Last {lines} lines):**\n\n```\n{content}\n```"
        
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    await reply_and_delete(event, msg)


async def handle_download_logs_command(event, parts):
    """处理 /download_logs [error]"""
    log_type = "app"
    if len(parts) > 1 and parts[1].lower() == "error":
        log_type = "error"
        
    from services.system_service import system_service
    file_path = system_service.get_log_file_path(log_type)
    
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    
    if file_path:
        await event.respond(file=file_path, message=f"📂 **{log_type.upper()} Log File**")
    else:
        await reply_and_delete(event, f"❌ Log file not found: {log_type}")

        
    # [Refactor] The actual implementation is already defined above as 'handle_db_optimize_command'
    # but we accidentally defined another one at the end of file.
    # We should use the robust one (lines 1826) instead of duplicate one.
    # Removing duplicate code blocks.

