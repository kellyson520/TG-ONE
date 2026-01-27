import asyncio
import re

# 导入新的过滤器系统
from filters.factory import get_filter_chain_factory
from repositories.db_operations import DBOperations
from models.models import ForwardMode
from core.helpers.common import check_keywords, get_sender_info

# 导入统一优化工具
from repositories.db_context import async_db_session, db_session, safe_db_operation
from core.helpers.error_handler import handle_errors, handle_telegram_errors, retry_on_failure
from core.helpers.forward_recorder import forward_recorder
from core.logging import get_logger, log_performance, log_user_action
from core.helpers.message_utils import get_message_handler
from core.cache.unified_cache import cached, get_smart_cache

logger = get_logger(__name__)


@log_performance("处理转发规则", threshold_seconds=5.0)
@log_user_action(
    "处理转发",
    extract_user_id=lambda client, event, chat_id, rule: getattr(
        event.sender, "id", "unknown"
    ),
)
@handle_errors(default_return=None)
async def process_forward_rule(client, event, chat_id, rule):
    """处理转发规则（用户模式） - 使用配置化过滤器链"""

    logger.log_operation(
        "开始处理转发规则（用户模式）",
        entity_id=rule.id,
        details=f"模式: {rule.forward_mode.value}",
    )

    try:
        # 使用配置化过滤器链，但可能使用简化配置
        factory = get_filter_chain_factory()

        # 为用户模式获取或创建简化的过滤器链
        filter_chain = _get_user_mode_filter_chain(factory, rule)

        # 执行过滤器链
        result = await filter_chain.process(client, event, chat_id, rule)

        logger.log_operation(
            f"用户模式过滤器链处理完成", entity_id=rule.id, details=f"结果: {result}"
        )
        return result

    except Exception as e:
        # 🚨【关键修改】增加显眼的警告日志
        logger.warning(
            f"🚨 过滤器链发生崩溃: {str(e)}。系统正在切换到【降级模式】(Fallback) 执行转发！"
        )
        logger.log_error("用户模式过滤器链处理异常", e, entity_id=rule.id)

        # 降级到原有逻辑
        return await _fallback_process_forward_rule(client, event, chat_id, rule)


def _get_user_mode_filter_chain(factory, rule):
    """
    为用户模式获取或创建简化的过滤器链

    Args:
        factory: 过滤器链工厂实例
        rule: 转发规则

    Returns:
        过滤器链实例
    """
    # 检查规则是否有用户模式专用配置
    user_mode_config = getattr(rule, "user_mode_filters", None)
    if user_mode_config:
        # 使用规则中定义的用户模式配置
        try:
            if isinstance(user_mode_config, str):
                import json

                config = json.loads(user_mode_config)
            else:
                config = user_mode_config

            if isinstance(config, list):
                return factory.create_chain_from_config(config, use_cache=True)
            elif isinstance(config, dict) and "filters" in config:
                return factory.create_chain_from_config(
                    config["filters"], use_cache=True
                )
        except Exception as e:
            logger.log_error("解析用户模式过滤器配置失败", e, entity_id=rule.id)

    # 使用简化的默认用户模式配置
    user_mode_filters = [
        "init",  # 初始化
        "keyword",  # 关键词过滤（核心）
        "replace",  # 文本替换（如果启用）
        "sender",  # 发送（简化版）
    ]

    # 根据规则设置调整用户模式过滤器
    if not rule.is_replace:
        user_mode_filters.remove("replace")

    # 如果启用了延迟处理，添加延迟过滤器
    if rule.enable_delay:
        user_mode_filters.insert(-1, "delay")  # 在sender之前添加

    return factory.create_chain_from_config(user_mode_filters, use_cache=True)


@handle_errors(default_return=None)
async def _fallback_process_forward_rule(client, event, chat_id, rule):
    """降级处理转发规则（原有逻辑）"""

    if not rule.enable_rule:
        logger.log_operation("规则已禁用", entity_id=rule.id, details="跳过处理")
        return

    logger.log_operation(
        "使用降级处理逻辑",
        entity_id=rule.id,
        details=f"模式: {rule.forward_mode.value}",
    )

    # 准备消息文本
    message_text = event.message.text or ""
    check_message_text = await _prepare_message_text(event, rule, message_text)

    # 检查关键词过滤
    should_forward = await check_keywords(rule, check_message_text)

    logger.log_operation(
        "关键词检查完成",
        entity_id=rule.id,
        details=f"结果: {'转发' if should_forward else '不转发'}",
    )

    if should_forward:
        await _execute_forward(client, event, rule)


@handle_errors(default_return="")
async def _prepare_message_text(event, rule, message_text):
    """准备消息文本 - 添加用户信息等"""
    check_message_text = message_text

    if rule.is_filter_user_info:
        sender_info = await get_sender_info(event, rule.id)
        if sender_info:
            check_message_text = f"{sender_info}:\n{message_text}"
            logger.log_operation("添加用户信息", entity_id=rule.id, details="成功")
        else:
            logger.log_operation(
                "获取发送者信息失败", entity_id=rule.id, level="warning"
            )

    return check_message_text


@handle_telegram_errors(default_return=None)
async def _execute_forward(client, event, rule):
    """执行转发逻辑 - 优化版本"""
    target_chat = rule.target_chat
    target_chat_id = int(target_chat.telegram_chat_id)

    logger.log_operation(
        "开始执行转发", entity_id=rule.id, details=f"目标: {target_chat_id}"
    )

    # 直接使用传统转发方法，不再依赖旧的managers
    if event.message.grouped_id:
        # 媒体组转发
        logger.log_operation(
            "媒体组转发", entity_id=rule.id, details=f"目标: {target_chat_id}"
        )
        # 使用Telethon原生的转发方法
        await client.forward_messages(
            target_chat_id, event.message, from_peer=event.chat_id
        )
    else:
        # 单条消息转发
        logger.log_operation(
            "单条消息转发", entity_id=rule.id, details=f"目标: {target_chat_id}"
        )
        await client.forward_messages(
            target_chat_id, event.message, from_peer=event.chat_id
        )

    # 记录转发
    await _record_forward(event, rule, target_chat_id)


# 去重和转发相关函数已移除，不再使用旧的managers
# 现在使用新的中间件架构处理去重和转发


@handle_errors(default_return=None)
async def _record_forward(event, rule, target_chat_id):
    """记录转发信息"""
    logger.debug(
        f"开始记录转发: rule_id={rule.id}, source={event.chat_id}, target={target_chat_id}"
    )
    try:
        result = await forward_recorder.record_forward(
            message_obj=event.message,
            source_chat_id=event.chat_id,
            target_chat_id=target_chat_id,
            rule_id=rule.id,
            forward_type="auto",
        )
        logger.debug(f"转发记录完成: result={result}")

        logger.log_operation("转发记录完成", entity_id=rule.id)

    except Exception as e:
        logger.log_error("记录转发", e, entity_id=rule.id)
