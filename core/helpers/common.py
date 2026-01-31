from datetime import datetime, timedelta
import logging
import os
from typing import Any, Optional, List, Tuple, Dict, Union, cast
from telethon.tl.types import ChannelParticipantsAdmins

from core.constants import AI_SETTINGS_TEXT, MEDIA_SETTINGS_TEXT
from core.helpers.auto_delete import reply_and_delete

logger = logging.getLogger(__name__)

from core.config import settings

async def get_user_id() -> int:
    """获取用户ID，确保配置已加载"""
    user_id = settings.USER_ID
    if not user_id:
        logger.error("未配置 USER_ID")
        raise ValueError("必须在 .env 文件或配置中设置 USER_ID")
    return int(user_id)

async def get_current_rule(event: Any) -> Optional[Tuple[Any, Any]]:
    """获取当前选中的规则 (Delegate to RuleQueryService)"""
    try:
        mod = __import__('services.rule_service', fromlist=['RuleQueryService'])
        RuleQueryService = mod.RuleQueryService

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

async def get_all_rules(event: Any) -> Optional[List[Any]]:
    """获取当前聊天的所有规则 (Delegate to RuleQueryService)"""
    try:
        mod = __import__('services.rule_service', fromlist=['RuleQueryService'])
        RuleQueryService = mod.RuleQueryService

        current_chat = await event.get_chat()
        chat_id = abs(current_chat.id)
        logger.info(f"获取当前聊天规则: {chat_id}")

        rules = await RuleQueryService.get_rules_for_target_chat(chat_id)

        if not rules:
            logger.info("未找到任何转发规则")
            await reply_and_delete(event, "当前聊天没有任何转发规则")
            return None

        logger.info(f"找到 {len(rules)} 条转发规则")
        return cast(Optional[List[Any]], rules)

    except Exception as e:
        logger.error(f"获取所有规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "获取规则时出错，请检查日志")
        return None

# 添加缓存字典
_admin_cache: Dict[str, Any] = {}
_CACHE_DURATION = timedelta(minutes=30)  # 缓存30分钟

async def get_channel_admins(client: Any, chat_id: Union[int, str]) -> Optional[List[int]]:
    """获取频道管理员列表，带缓存机制"""
    current_time = datetime.now()

    chat_id_str = str(chat_id)
    if chat_id_str in _admin_cache:
        cache_data = _admin_cache[chat_id_str]
        if current_time - cache_data["timestamp"] < _CACHE_DURATION:
            return cast(List[int], cache_data["admin_ids"])

    try:
        admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
        admin_ids = [admin.id for admin in admins]
        _admin_cache[chat_id_str] = {"admin_ids": admin_ids, "timestamp": current_time}
        return admin_ids
    except Exception as e:
        logger.error(f"获取频道管理员列表失败: {str(e)}")
        return None

async def is_admin(event: Any, client: Optional[Any] = None) -> bool:
    """检查用户是否为管理员 (Delegate to UserService)"""
    try:
        mod = __import__('services.user_service', fromlist=['user_service'])
        user_service = mod.user_service
        return bool(await user_service.is_admin(event.sender_id, event, client))
    except Exception as e:
        logger.error(f"检查管理员权限时出错: {str(e)}")
        return False



async def get_sender_info(event: Any, rule_id: Any) -> Optional[str]:
    """获取发送者信息 (保持原逻辑，涉及大量 Telethon 交互)"""
    try:
        mod_batch = __import__('services.batch_user_service', fromlist=['get_batch_user_service'])
        get_batch_user_service = mod_batch.get_batch_user_service
        mod_api = __import__('services.network.api_optimization', fromlist=['get_api_optimizer'])
        get_api_optimizer = mod_api.get_api_optimizer

        batch_service = get_batch_user_service()
        api_optimizer = get_api_optimizer()

        if api_optimizer:
            user_info = await api_optimizer.optimize_user_info_for_message(event)
            if user_info and user_info.get("sender_name"):
                return str(user_info["sender_name"])

        if hasattr(event.message, "sender_chat") and event.message.sender_chat:
            sender = event.message.sender_chat
            return str(sender.title) if hasattr(sender, "title") else None
        elif event.sender:
            sender = event.sender
            return str(sender.title) if hasattr(sender, "title") else f"{sender.first_name or ''} {sender.last_name or ''}".strip()

        if event.sender_id:
            users_info = await batch_service.get_users_info([event.sender_id])
            if str(event.sender_id) in users_info:
                user_data = users_info[str(event.sender_id)]
                return f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()

        return None
    except Exception as e:
        logger.error(f"获取发送者信息出错: {str(e)}")
        return None

async def check_and_clean_chats(rule: Optional[Any] = None) -> int:
    """Delegate to RuleLogicService"""
    try:
        from core.container import container
        return int(await container.rule_management_service.logic.cleanup_orphan_chats(rule))
    except Exception as e:
        logger.error(f"检查和清理聊天记录时出错: {str(e)}")
        return 0

def get_admin_list() -> List[int]:
    if settings.ADMIN_IDS:
        if isinstance(settings.ADMIN_IDS, list):
            return settings.ADMIN_IDS
        # 如果是字符串（虽然 Pydantic 应该已经转换了），则处理一下
        return [int(admin.strip()) for admin in str(settings.ADMIN_IDS).split(",") if admin.strip()]
    
    if not settings.USER_ID:
        raise ValueError("必须在配置中设置 USER_ID 或 ADMIN_IDS")
    return [int(settings.USER_ID)]

async def check_keywords(rule: Any, message_text: str, event: Optional[Any] = None) -> bool:
    """Delegate to RuleFilterService"""
    mod = __import__('services.rule.filter', fromlist=['RuleFilterService'])
    return bool(await mod.RuleFilterService.check_keywords(rule, message_text, event))

async def process_user_info(event: Any, rule_id: Any, message_text: str) -> str:
    """Delegate to UserService"""
    try:
        mod = __import__('services.user_service', fromlist=['user_service'])
        user_service = mod.user_service
        return str(await user_service.process_user_info(event, rule_id, message_text))
    except Exception as e:
        logger.error(f"处理用户信息失败: {str(e)}")
        return message_text

async def get_db_ops() -> Any:
    mod = __import__('repositories.db_operations', fromlist=['DBOperations'])
    return await mod.DBOperations.create()

async def get_user_client() -> Any:
    from core.container import container
    return container.user_client

async def get_bot_client() -> Any:
    from core.container import container
    return container.bot_client

async def get_main_module() -> Any:
    from core.container import container
    class MainModuleWrapper:
        @property
        def bot_client(self) -> Any: return container.bot_client
        @property
        def user_client(self) -> Any: return container.user_client
    return MainModuleWrapper()

def get_session() -> Any:
    """Delegate to core.db_factory"""
    mod = __import__('core.db_factory', fromlist=['get_session'])
    return mod.get_session()

