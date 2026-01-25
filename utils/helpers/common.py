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
    """获取当前选中的规则"""
    try:
        from services.rule_service import RuleQueryService

        # 直接使用服务
        result = await RuleQueryService.get_current_rule_for_chat(event)

        if result is None:
            logger.info("未找到当前聊天或未选择源聊天")
            await reply_and_delete(event, "请先使用 /switch 选择一个源聊天")
            return None

        rule, source_chat = result
        logger.info(f"找到转发规则 ID: {rule.id}，源聊天: {source_chat.name}")
        return rule, source_chat

    except Exception as e:
        logger.error(f"获取当前规则时出错: {str(e)}", exc_info=True)
        await reply_and_delete(event, "获取当前规则时出错，请检查日志")
        return None


async def get_all_rules(event):
    """获取当前聊天的所有规则"""
    try:
        from services.rule_service import RuleQueryService

        # 获取当前聊天ID
        current_chat = await event.get_chat()
        chat_id = abs(current_chat.id)
        logger.info(f"获取当前聊天规则: {chat_id}")

        # 使用服务获取规则
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

    # 检查缓存是否存在且未过期
    if chat_id in _admin_cache:
        cache_data = _admin_cache[chat_id]
        if current_time - cache_data["timestamp"] < _CACHE_DURATION:
            return cache_data["admin_ids"]

    # 缓存不存在或已过期，重新获取管理员列表
    try:
        admins = await client.get_participants(
            chat_id, filter=ChannelParticipantsAdmins
        )
        admin_ids = [admin.id for admin in admins]

        # 更新缓存
        _admin_cache[chat_id] = {"admin_ids": admin_ids, "timestamp": current_time}
        return admin_ids
    except Exception as e:
        logger.error(f"获取频道管理员列表失败: {str(e)}")
        return None


async def is_admin(event, client=None):
    """检查用户是否为频道/群组管理员

    Args:
        event: 事件对象
        client: 客户端对象（可选，如未提供则从container获取）
    Returns:
        bool: 是否是管理员
    """
    try:
        # 获取所有机器人管理员列表
        bot_admins = get_admin_list()
        user_id = event.sender_id  # 使用 sender_id 作为主要ID来源
        
        # 1. 首先检查.env配置的管理员列表
        if user_id in bot_admins:
            logger.debug(f"用户 {user_id} 在.env管理员列表中")
            return True
        
        # 2. 检查数据库User表中是否绑定了该Telegram ID且是管理员
        try:
            from core.container import container
            
            user = await container.user_repo.get_admin_by_telegram_id(str(user_id))
            if user:
                logger.debug(f"用户 {user_id} 在数据库管理员列表中")
                return True
        except Exception as db_e:
            logger.warning(f"检查数据库管理员失败: {str(db_e)}")
        
        # 3. 检查是否有message属性，针对不同类型的消息进行处理
        if not hasattr(event, "message"):
            # 没有message属性,是回调处理
            logger.info(f"用户 {user_id} 非管理员，操作已被忽略")
            return False

        # 如果未提供client，从container获取
        if not client:
            from core.container import container
            client = container.user_client

        message = event.message

        if message.is_channel and not message.is_group:
            # 获取频道管理员列表（使用缓存）
            channel_admins = await get_channel_admins(client, event.chat_id)
            if channel_admins is None:
                return False

            # 检查机器人管理员是否在频道管理员列表中
            admin_in_channel = any(
                admin_id in channel_admins for admin_id in bot_admins
            )
            if not admin_in_channel:
                logger.info("机器人管理员不在频道管理员列表中，已忽略")
                return False
            return True
        else:
            # 检查发送者ID
            logger.info(f"发送者ID：{user_id}，非管理员，操作已忽略")
            return False
    except Exception as e:
        logger.error(f"检查管理员权限时出错: {str(e)}")
        return False


async def get_media_settings_text():
    """生成媒体设置页面的文本"""
    return MEDIA_SETTINGS_TEXT


async def get_ai_settings_text(rule):
    """生成AI设置页面的文本"""
    ai_prompt = rule.ai_prompt or os.getenv("DEFAULT_AI_PROMPT", "未设置")
    summary_prompt = rule.summary_prompt or os.getenv(
        "DEFAULT_SUMMARY_PROMPT", "未设置"
    )

    return AI_SETTINGS_TEXT.format(ai_prompt=ai_prompt, summary_prompt=summary_prompt)


async def get_sender_info(event, rule_id):
    """
    获取发送者信息 - 完全使用官方API优化版本

    Args:
        event: 消息事件
        rule_id: 规则ID

    Returns:
        str: 发送者信息
    """
    try:
        logger.info("开始获取发送者信息 (优化版本)")

        # 使用批量用户服务获取优化的用户信息
        from services.batch_user_service import get_batch_user_service
        from utils.network.api_optimization import get_api_optimizer

        batch_service = get_batch_user_service()
        api_optimizer = get_api_optimizer()

        # 先尝试使用优化的API
        if api_optimizer:
            user_info = await api_optimizer.optimize_user_info_for_message(event)
            if user_info and user_info.get("sender_name"):
                logger.info(f"使用优化API获取发送者信息: {user_info['sender_name']}")
                return user_info["sender_name"]

        # 快速检查事件中已有的发送者信息
        if hasattr(event.message, "sender_chat") and event.message.sender_chat:
            sender = event.message.sender_chat
            sender_name = sender.title if hasattr(sender, "title") else None
            if sender_name:
                logger.info(f"使用频道信息: {sender_name}")
                return sender_name

        elif event.sender:
            sender = event.sender
            sender_name = (
                sender.title
                if hasattr(sender, "title")
                else f"{sender.first_name or ''} {sender.last_name or ''}".strip()
            )
            if sender_name:
                logger.info(f"使用事件发送者信息: {sender_name}")
                return sender_name

        # 使用批量用户服务获取用户信息
        if event.sender_id:
            users_info = await batch_service.get_users_info([event.sender_id])
            if str(event.sender_id) in users_info:
                user_data = users_info[str(event.sender_id)]
                sender_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                if sender_name:
                    logger.info(f"使用批量服务获取发送者信息: {sender_name}")
                    return sender_name

        # 最后的降级处理 - peer_id（避免单个API调用）
        if hasattr(event.message, "peer_id") and event.message.peer_id:
            peer = event.message.peer_id
            if hasattr(peer, "channel_id"):
                # 使用批量服务而不是单个get_entity
                try:
                    users_info = await batch_service.get_users_info([peer.channel_id])
                    if str(peer.channel_id) in users_info:
                        user_data = users_info[str(peer.channel_id)]
                        sender_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                        if sender_name:
                            logger.info(f"使用peer_id批量获取: {sender_name}")
                            return sender_name
                except Exception as ce:
                    logger.error(f"批量获取peer_id信息失败: {str(ce)}")

        logger.warning(f"规则 ID: {rule_id} - 无法获取发送者信息")
        return None

    except Exception as e:
        logger.error(f"获取发送者信息出错: {str(e)}")
        return None


async def check_and_clean_chats(rule=None):
    """
    检查并清理不再与任何规则关联的聊天记录
    
    Args:
        rule: 被删除的规则对象（可选），如果提供则从中获取聊天ID
        
    Returns:
        int: 删除的聊天记录数量
    """
    try:
        from core.container import container
        return await container.rule_mgmt_service.cleanup_orphan_chats(rule)
    except Exception as e:
        logger.error(f"检查和清理聊天记录时出错: {str(e)}")
        return 0


def get_admin_list():
    """获取管理员ID列表，如果ADMINS为空则使用USER_ID"""
    admin_str = os.getenv("ADMINS", "")
    if not admin_str:
        user_id = os.getenv("USER_ID")
        if not user_id:
            logger.error("未设置 USER_ID 环境变量")
            raise ValueError("必须在 .env 文件中设置 USER_ID")
        return [int(user_id)]
    return [int(admin.strip()) for admin in admin_str.split(",") if admin.strip()]


async def check_keywords(rule, message_text, event=None):
    """
    检查消息是否匹配关键字规则

    Args:
        rule: 转发规则对象，包含 forward_mode 和 keywords 属性
        message_text: 要检查的消息文本
        event: 可选的消息事件对象

    Returns:
        bool: 是否应该转发消息
    """
    reverse_blacklist = rule.enable_reverse_blacklist
    reverse_whitelist = rule.enable_reverse_whitelist
    logger.info(f"反转黑名单: {reverse_blacklist}, 反转白名单: {reverse_whitelist}")

    # 合并媒体文件名等可检索信息，提升媒体消息的匹配率
    try:
        if (
            event
            and hasattr(event, "message")
            and getattr(event.message, "media", None)
        ):
            doc = getattr(event.message, "document", None)
            if doc and hasattr(doc, "attributes") and doc.attributes:
                for attr in doc.attributes:
                    file_name = getattr(attr, "file_name", None)
                    if file_name:
                        try:
                            # 避免重复追加
                            if file_name not in (message_text or ""):
                                message_text = (
                                    f"{message_text}\n{file_name}"
                                    if message_text
                                    else file_name
                                )
                        except Exception:
                            pass
                        break
    except Exception:
        # 文件名获取失败不应影响主流程
        pass

    # 处理用户信息过滤
    if rule.is_filter_user_info and event:
        message_text = await process_user_info(event, rule.id, message_text)

    logger.info("开始检查关键字规则")
    logger.info(f"当前转发模式: {rule.forward_mode}")

    forward_mode = rule.forward_mode
    # 仅白名单模式
    if forward_mode == ForwardMode.WHITELIST:
        return await process_whitelist_mode(rule, message_text, reverse_blacklist)

    # 仅黑名单模式
    elif forward_mode == ForwardMode.BLACKLIST:
        return await process_blacklist_mode(rule, message_text, reverse_whitelist)

    # 先白后黑模式
    elif forward_mode == ForwardMode.WHITELIST_THEN_BLACKLIST:
        return await process_whitelist_then_blacklist_mode(
            rule, message_text, reverse_blacklist
        )

    # 先黑后白模式
    elif forward_mode == ForwardMode.BLACKLIST_THEN_WHITELIST:
        return await process_blacklist_then_whitelist_mode(
            rule, message_text, reverse_whitelist
        )

    logger.error(f"未知的转发模式: {forward_mode}")
    return False


async def process_whitelist_mode(rule, message_text, reverse_blacklist):
    """处理仅白名单模式"""
    logger.info("进入仅白名单模式")
    should_forward = False

    # 使用快速匹配 (AC自动机优化)
    whitelist_keywords = [k for k in rule.keywords if not k.is_blacklist]
    if await check_keywords_fast(whitelist_keywords, message_text, rule.id):
        should_forward = True

    if not should_forward:
        logger.info("未匹配到普通白名单关键词，不转发")
        return False

    # 如果启用了黑名单反转，还需要匹配反转后的黑名单（作为第二重白名单）
    if reverse_blacklist:
        logger.info("检查反转后的黑名单关键词（作为白名单）")
        reversed_blacklist = [k for k in rule.keywords if k.is_blacklist]
        logger.info(f"反转后的黑名单关键词: {[k.keyword for k in reversed_blacklist]}")

        if not reversed_blacklist:
            # 无黑名单关键词可用于第二重白名单时，跳过该约束，避免误杀
            logger.info("反转黑名单启用但没有黑名单关键词，跳过第二重白名单要求")
        else:
            reversed_blacklist = [k for k in rule.keywords if k.is_blacklist]
            if not await check_keywords_fast(reversed_blacklist, message_text, rule.id):
                logger.info("未匹配到反转后的黑名单关键词，不转发")
                return False

    logger.info("所有白名单条件都满足，允许转发")
    return True


async def process_blacklist_mode(rule, message_text, reverse_whitelist):
    """处理仅黑名单模式"""
    logger.info("进入仅黑名单模式")

    # 检查普通黑名单关键词
    blacklist_keywords = [k for k in rule.keywords if k.is_blacklist]
    if await check_keywords_fast(blacklist_keywords, message_text, rule.id):
        logger.info("匹配到黑名单关键词，不转发")
        return False

    # 如果启用了白名单反转，检查反转后的白名单（作为黑名单）
    if reverse_whitelist:
        reversed_whitelist = [k for k in rule.keywords if not k.is_blacklist]
        if await check_keywords_fast(reversed_whitelist, message_text, rule.id):
            logger.info("匹配到反转后的白名单关键词，不转发")
            return False

    logger.info("未匹配到任何黑名单关键词，允许转发")
    return True


async def check_keywords_fast(keywords, message_text, rule_id=None):
    """
    快速批量检查关键词是否匹配 (使用 AC 自动机优化)
    
    Args:
        keywords: 关键词对象列表
        message_text: 待检查文本
        rule_id: 规则ID (用于缓存自动机)
        
    Returns:
        bool: 是否有任何匹配
    """
    if not keywords or not message_text:
        return False

    # 分离正则和固定字符串
    fixed_kws = []
    regex_kws = []
    for k in keywords:
        if k.is_regex:
            regex_kws.append(k)
        else:
            fixed_kws.append(k)
            
    # 1. 首先检查正则 (通常数量较少)
    for k in regex_kws:
        try:
            if re.search(k.keyword, message_text, re.I): # 默认忽略大小写
                return True
        except Exception as e:
            logger.error(f"正则匹配出错: {k.keyword}, {e}")
            
    # 2. 使用 AC 自动机检查固定字符串 (O(N))
    if fixed_kws:
        # 提取文本列表用于构建自动机
        kw_list = [k.keyword.lower() for k in fixed_kws]
        try:
            from utils.processing.ac_automaton import ACManager
            # rule_id 若为空则不使用长期缓存，仅单次使用
            # 但通常 rule_id 都有
            target_id = rule_id or hash(tuple(kw_list))
            ac = ACManager.get_automaton(target_id, kw_list)
            if ac.has_any_match(message_text.lower()):
                return True
        except Exception as e:
            logger.error(f"AC自动机匹配出错: {e}")
            # 降级到传统循环匹配
            for kw in fixed_kws:
                if kw.keyword.lower() in message_text.lower():
                    return True
                    
    return False

async def check_keyword_match(keyword, message_text):
    """检查单个关键词是否匹配 (保留兼容性)"""
    # logger.info(f"检查关键字: {keyword.keyword} (正则: {keyword.is_regex})")
    if keyword.is_regex:
        try:
            if re.search(keyword.keyword, message_text, re.I):
                return True
        except re.error:
            logger.error(f"正则表达式错误: {keyword.keyword}")
    else:
        if keyword.keyword.lower() in message_text.lower():
            return True
    return False


async def process_user_info(event, rule_id, message_text):
    """处理用户信息过滤 - 官方API优化版本"""
    try:
        # 使用批量用户服务获取优化的用户信息
        from services.batch_user_service import get_batch_user_service

        batch_service = get_batch_user_service()

        # 先尝试使用优化的API
        user_info_text = await batch_service.format_user_info_for_message(event)
        if user_info_text:
            logger.info(f"使用优化API成功获取用户信息: {user_info_text.strip()}")
            return f"{user_info_text}{message_text}"

        # 降级到原有逻辑
        username = await get_sender_info(event, rule_id)
        name = None

        if hasattr(event.message, "sender_chat") and event.message.sender_chat:
            sender = event.message.sender_chat
            name = sender.title if hasattr(sender, "title") else None
        elif event.sender:
            sender = event.sender
            name = (
                sender.title
                if hasattr(sender, "title")
                else f"{sender.first_name or ''} {sender.last_name or ''}".strip()
            )

        if username and name:
            logger.info(f"降级方法获取用户信息: {username} {name}")
            return f"{username} {name}:\n{message_text}"
        elif username:
            logger.info(f"降级方法获取用户信息: {username}")
            return f"{username}:\n{message_text}"
        elif name:
            logger.info(f"降级方法获取用户信息: {name}")
            return f"{name}:\n{message_text}"
        else:
            logger.warning(f"规则 ID: {rule_id} - 无法获取发送者信息")
            return message_text

    except Exception as e:
        logger.error(f"处理用户信息失败: {str(e)}")
        return message_text


async def process_whitelist_then_blacklist_mode(rule, message_text, reverse_blacklist):
    """处理先白后黑模式

    先检查白名单（必须匹配），然后检查黑名单（不能匹配）
    如果启用黑名单反转，则黑名单变成第二重白名单（必须匹配）
    """
    logger.info("进入先白后黑模式")

    whitelist_keywords = [k for k in rule.keywords if not k.is_blacklist]
    if not await check_keywords_fast(whitelist_keywords, message_text, rule.id):
        logger.info("未匹配到白名单关键词，不转发")
        return False
        
    # 根据反转设置处理黑名单
    blacklist_keywords = [k for k in rule.keywords if k.is_blacklist]
    
    if reverse_blacklist:
        # 黑名单反转为白名单，必须匹配才转发
        if not await check_keywords_fast(blacklist_keywords, message_text, rule.id):
            logger.info("未匹配到反转后的黑名单关键词，不转发")
            return False
    else:
        # 正常黑名单，匹配则不转发
        if await check_keywords_fast(blacklist_keywords, message_text, rule.id):
            logger.info("匹配到黑名单关键词，不转发")
            return False
            
    logger.info("所有条件都满足，允许转发")
    return True


async def process_blacklist_then_whitelist_mode(rule, message_text, reverse_whitelist):
    """处理先黑后白模式

    先检查黑名单（不能匹配），然后检查白名单（必须匹配）
    如果启用白名单反转，则白名单变成第二重黑名单（不能匹配）
    """
    logger.info("进入先黑后白模式")

    blacklist_keywords = [k for k in rule.keywords if k.is_blacklist]
    if await check_keywords_fast(blacklist_keywords, message_text, rule.id):
        logger.info("匹配到黑名单关键词，不转发")
        return False

    # 处理白名单
    whitelist_keywords = [k for k in rule.keywords if not k.is_blacklist]

    if reverse_whitelist:
        # 白名单反转为黑名单，匹配则不转发
        if await check_keywords_fast(whitelist_keywords, message_text, rule.id):
            logger.info("匹配到反转后的白名单关键词，不转发")
            return False
    else:
        # 正常白名单，必须匹配才转发
        if not await check_keywords_fast(whitelist_keywords, message_text, rule.id):
            logger.info("未匹配到白名单关键词，不转发")
            return False

    logger.info("所有条件都满足，允许转发")
    return True


async def get_db_ops():
    """获取数据库操作实例"""
    from utils.db.db_operations import DBOperations
    return await DBOperations.create()


async def get_user_client():
    """获取用户客户端实例"""
    from core.container import container
    return container.user_client


async def get_bot_client():
    """获取机器人客户端实例"""
    from core.container import container
    return container.bot_client


async def get_main_module():
    """获取主模块实例 (用于兼容旧代码)"""
    from core.container import container
    
    class MainModuleWrapper:
        @property
        def bot_client(self):
            return container.bot_client

        @property
        def user_client(self):
            return container.user_client

    return MainModuleWrapper()
