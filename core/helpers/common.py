from datetime import datetime, timedelta
import logging
import os
import re
from telethon.tl.types import ChannelParticipantsAdmins

from enums.enums import ForwardMode
from utils.core.constants import AI_SETTINGS_TEXT, MEDIA_SETTINGS_TEXT
from utils.processing.auto_delete import reply_and_delete

logger = logging.getLogger(__name__)

async def get_user_id():
    """获取用户ID，确保环境变量已加载"""
    user_id_str = os.getenv("USER_ID")
    if not user_id_str:
        logger.error("未设置 USER_ID 环境变量")
        raise ValueError("必须在 .env 文件中设置 USER_ID")
    return int(user_id_str)

async def get_current_rule(event):
    """获取当前选中的规则 (Delegate to RuleQueryService)"""
    try:
        from services.rule_service import RuleQueryService

        result = await RuleQueryService.get_current_rule_for_chat(event)

        if result is None:
            logger.info("未找到当前聊天或未选择源聊天")
            await reply_and_delete(event, "请先使用 /switch 选择一个源聊天")
            return None

        rule_dto, source_chat_dto = result
        logger.info(f"找到转发规则 ID: {rule_dto.id}，源聊天: {source_chat_dto.name}")
        return rule_dto, source_chat_dto

    except Exception as e:
        logger.error(f"获取当前规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "获取当前规则时出错，请检查日志")
        return None

async def get_all_rules(event):
    """获取当前聊天的所有规则 (Delegate to RuleQueryService)"""
    try:
        from services.rule_service import RuleQueryService

        current_chat = await event.get_chat()
        chat_id = abs(current_chat.id)
        logger.info(f"获取当前聊天规则: {chat_id}")

        rules = await RuleQueryService.get_rules_for_target_chat(chat_id)

        if not rules:
            logger.info("未找到任何转发规则")
            await reply_and_delete(event, "当前聊天没有任何转发规则")
            return None

        logger.info(f"找到 {len(rules)} 条转发规则")
        return rules

    except Exception as e:
        logger.error(f"获取所有规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "获取规则时出错，请检查日志")
        return None

# 添加缓存字典
_admin_cache = {}
_CACHE_DURATION = timedelta(minutes=30)  # 缓存30分钟

async def get_channel_admins(client, chat_id):
    """获取频道管理员列表，带缓存机制"""
    current_time = datetime.now()

    if chat_id in _admin_cache:
        cache_data = _admin_cache[chat_id]
        if current_time - cache_data["timestamp"] < _CACHE_DURATION:
            return cache_data["admin_ids"]

    try:
        admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
        admin_ids = [admin.id for admin in admins]
        _admin_cache[chat_id] = {"admin_ids": admin_ids, "timestamp": current_time}
        return admin_ids
    except Exception as e:
        logger.error(f"获取频道管理员列表失败: {str(e)}")
        return None

async def is_admin(event, client=None):
    """检查用户是否为管理员 (Delegate to UserService)"""
    try:
        from services.user_service import user_service
        return await user_service.is_admin(event.sender_id, event, client)
    except Exception as e:
        logger.error(f"检查管理员权限时出错: {str(e)}")
        return False

async def get_media_settings_text():
    return MEDIA_SETTINGS_TEXT

async def get_ai_settings_text(rule):
    ai_prompt = rule.ai_prompt or os.getenv("DEFAULT_AI_PROMPT", "未设置")
    summary_prompt = rule.summary_prompt or os.getenv("DEFAULT_SUMMARY_PROMPT", "未设置")
    return AI_SETTINGS_TEXT.format(ai_prompt=ai_prompt, summary_prompt=summary_prompt)

async def get_sender_info(event, rule_id):
    """获取发送者信息 (保持原逻辑，涉及大量 Telethon 交互)"""
    try:
        from services.batch_user_service import get_batch_user_service
        from services.network.api_optimization import get_api_optimizer

        batch_service = get_batch_user_service()
        api_optimizer = get_api_optimizer()

        if api_optimizer:
            user_info = await api_optimizer.optimize_user_info_for_message(event)
            if user_info and user_info.get("sender_name"):
                return user_info["sender_name"]

        if hasattr(event.message, "sender_chat") and event.message.sender_chat:
            sender = event.message.sender_chat
            return sender.title if hasattr(sender, "title") else None
        elif event.sender:
            sender = event.sender
            return sender.title if hasattr(sender, "title") else f"{sender.first_name or ''} {sender.last_name or ''}".strip()

        if event.sender_id:
            users_info = await batch_service.get_users_info([event.sender_id])
            if str(event.sender_id) in users_info:
                user_data = users_info[str(event.sender_id)]
                return f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()

        return None
    except Exception as e:
        logger.error(f"获取发送者信息出错: {str(e)}")
        return None

async def check_and_clean_chats(rule=None):
    """Delegate to RuleLogicService"""
    try:
        from core.container import container
        return await container.rule_management_service.logic.cleanup_orphan_chats(rule)
    except Exception as e:
        logger.error(f"检查和清理聊天记录时出错: {str(e)}")
        return 0

def get_admin_list():
    admin_str = os.getenv("ADMINS", "")
    if not admin_str:
        user_id = os.getenv("USER_ID")
        if not user_id:
            raise ValueError("必须在 .env 文件中设置 USER_ID")
        return [int(user_id)]
    return [int(admin.strip()) for admin in admin_str.split(",") if admin.strip()]

async def check_keywords(rule, message_text, event=None):
    """Delegate to RuleFilterService"""
    from services.rule.filter import RuleFilterService
    return await RuleFilterService.check_keywords(rule, message_text, event)

async def process_user_info(event, rule_id, message_text):
    """Delegate to UserService"""
    try:
        from services.user_service import user_service
        return await user_service.process_user_info(event, rule_id, message_text)
    except Exception as e:
        logger.error(f"处理用户信息失败: {str(e)}")
        return message_text

async def get_db_ops():
    from repositories.db_operations import DBOperations
    return await DBOperations.create()

async def get_user_client():
    from core.container import container
    return container.user_client

async def get_bot_client():
    from core.container import container
    return container.bot_client

async def get_main_module():
    from core.container import container
    class MainModuleWrapper:
        @property
        def bot_client(self): return container.bot_client
        @property
        def user_client(self): return container.user_client
    return MainModuleWrapper()
