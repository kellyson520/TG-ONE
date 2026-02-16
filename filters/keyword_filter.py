import logging
from core.helpers.common import get_main_module
from filters.base_filter import BaseFilter

from services.network.telegram_api_optimizer import api_optimizer
from core.helpers.error_handler import handle_errors

logger = logging.getLogger(__name__)

class KeywordFilter(BaseFilter):
    """
    关键字过滤器，检查消息是否包含指定关键字
    """
    
    async def _process(self, context):
        """
        检查消息是否包含规则中的关键字
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 若消息应继续处理则返回True，否则返回False
        """
        rule = context.rule
        message_text = context.message_text
        event = context.event

        # 1. 发送者校验 (支持 sender_id 和 sender_name 正则)
        sender_ok = self._check_sender(rule, context)
        if not sender_ok:
            logger.debug(f"发送者校验未通过: RuleID={getattr(rule, 'id', 'N/A')}")
            context.errors.append("发送者不匹配")
            return False

        # 2. 关键词校验 (增强模式)
        keyword_ok = await self._enhanced_keyword_check(rule, message_text, event)
        if not keyword_ok:
            context.errors.append("关键词过滤拦截")
            return False
            
        # ⚠️ 注意: 智能去重已迁移至 DedupMiddleware
        return True
    
    def _check_sender(self, rule, context) -> bool:
        """校验发送者是否匹配规则要求"""
        required_sender = getattr(rule, 'required_sender_id', None)
        required_sender_regex = getattr(rule, 'required_sender_regex', None)
        
        # 如果没有发送者限制，直接通过
        if required_sender is None and not required_sender_regex:
            return True
            
        sender_id_val = getattr(context, 'sender_id', None)
        sender_name_val = getattr(context, 'sender_name', '') or ''
        
        # 校验 ID
        if required_sender is not None:
            if str(sender_id_val) != str(required_sender):
                return False
                
        # 校验名称正则
        if required_sender_regex:
            import re
            try:
                if not re.search(required_sender_regex, sender_name_val, re.I):
                    return False
            except Exception as e:
                logger.error(f"发送者名称正则匹配出错: {e}")
                return False # 正则错误视为不匹配
                
        return True

    async def _enhanced_keyword_check(self, rule, message_text, event):
        """
        增强的关键词检查
        
        Args:
            rule: 转发规则
            message_text: 消息文本
            event: 消息事件
            
        Returns:
            bool: 是否通过关键词检查
        """
        from services.rule.filter import RuleFilterService
        try:
            # 使用 Service 进行关键词检查 (已包含 AC 自动机和正则优化)
            # 移除了会导致“全部转发”漏洞的 API 历史搜索逻辑
            return await RuleFilterService.check_keywords(rule, message_text, event)
        except Exception as e:
            logger.error(f"关键词检查发生异常: {str(e)}")
            return False

    
    @handle_errors(default_return=False)
    async def _check_smart_duplicate(self, context, rule):
        """
        检查智能去重
        
        Args:
            context: 消息上下文
            rule: 转发规则
            
        Returns:
            bool: 是否为重复消息
        """
        from services.dedup.engine import smart_deduplicator
        
        # 1. 智能去重基础配置
        window_hours = getattr(rule, 'dedup_time_window_hours', 24)
        if window_hours is None or window_hours < 0:
            window_hours = 24
            
        rule_config = {
            'enable_time_window': getattr(rule, 'enable_time_window_dedup', True),
            'time_window_hours': window_hours,
            'similarity_threshold': getattr(rule, 'similarity_threshold', 0.85),
            'enable_content_hash': getattr(rule, 'enable_content_hash_dedup', True),
            'enable_smart_similarity': getattr(rule, 'enable_smart_similarity', True),
        }

        # [修复核心]: 如果消息没有文本，强制禁用文本类去重策略
        # 这防止了空字符串生成相同的哈希值，导致所有无文本消息被误判为重复
        # 优先使用 context.message_text (经过预处理的文本)
        current_text = getattr(context, 'message_text', None)
        if not current_text or not str(current_text).strip():
            rule_config['enable_content_hash'] = False
            rule_config['enable_smart_similarity'] = False
            logger.debug(f"消息无文本，已禁用文本去重策略以防止误判: RuleID={getattr(rule, 'id', 'N/A')}")
        
        # [Fix] 安全获取目标聊天 ID
        target_chat = getattr(rule, 'target_chat', None)
        if not target_chat:
             logger.debug(f"无法获取目标聊天信息，跳过智能去重检查: 规则ID={getattr(rule, 'id', 'N/A')}")
             return False 
             
        target_chat_id = int(target_chat.telegram_chat_id)
        
        # [Optimization] 如果媒体已被全局屏蔽，去重时跳过媒体维度检查，仅保留文本维度
        skip_media_sig = getattr(context, 'media_blocked', False)
        if skip_media_sig:
             logger.info(f"媒体已被屏蔽，智能去重将跳过媒体签名检查: 规则ID={getattr(rule, 'id', 'N/A')}")

        logger.debug(f"正在进行智能去重检查: chat={target_chat_id}, config={rule_config}, skip_media_sig={skip_media_sig}")
        
        # 2. 执行去重检查
        is_duplicate, reason = await smart_deduplicator.check_duplicate(
            context.event.message, target_chat_id, rule_config, skip_media_sig=skip_media_sig
        )
        
        if is_duplicate:
            logger.info(f"智能去重命中，跳过发送: {reason}")
            
        return is_duplicate
    
    @handle_errors(default_return=None)
    async def _handle_duplicate_message_deletion(self, context, rule):
        """
        处理重复消息的删除
        
        Args:
            context: 消息上下文
            rule: 转发规则
        """
        if not getattr(rule, 'allow_delete_source_on_dedup', False):
            return
            
        await self._delete_source_message(context)
        await self._send_dedup_notification(context, rule)
    
    @handle_errors(default_return=None)
    async def _delete_source_message(self, context):
        """
        删除源消息
        
        Args:
            context: 消息上下文
        """
        main = await get_main_module()
        user_client = main.user_client
        
        if context.event.message.grouped_id:
            # 使用统一媒体组服务删除媒体组
            from services.media_service import media_service
            
            if media_service:
                # 使用媒体服务删除
                success = await media_service.delete_media_group(
                    context.event.chat_id, context.event.message.id, context.event.message.grouped_id
                )
                if not success:
                    logger.warning(f'删除媒体组失败 grouped_id: {context.event.message.grouped_id}')
            else:
                # 降级到传统方法
                logger.warning("媒体组管理器未初始化，使用传统方法删除媒体组消息")
                async for message in user_client.iter_messages(
                    context.event.chat_id,
                    min_id=context.event.message.id - 10,
                    max_id=context.event.message.id + 10,
                    reverse=True
                ):
                    if message.grouped_id == context.event.message.grouped_id:
                        await message.delete()
        else:
            # 删除单条消息
            msg = await user_client.get_messages(context.event.chat_id, ids=context.event.message.id)
            await msg.delete()
    
    @handle_errors(default_return=None)
    async def _send_dedup_notification(self, context, rule):
        """
        发送去重通知消息
        
        Args:
            context: 消息上下文
            rule: 转发规则
        """
        main = await get_main_module()
        bot_client = main.bot_client
        
        # 获取目标聊天实体
        target_entity = await self._get_target_entity(rule, context.event.chat_id)
        
        # 发送去重提示消息到目标聊天
        dedup_msg = await bot_client.send_message(
            target_entity,
            "🧹 已去重，重复消息已删除"
        )
        
        # 设置定时撤回
        await self._schedule_message_deletion(dedup_msg, 5.0)
    
    @handle_errors(default_return=None)
    async def _get_target_entity(self, rule, fallback_chat_id):
        """
        获取目标实体
        
        Args:
            rule: 转发规则
            fallback_chat_id: 备用聊天ID
            
        Returns:
            目标实体ID
        """
        target_chat_id_raw = getattr(rule.target_chat, 'telegram_chat_id', None)
        if target_chat_id_raw is not None:
            from core.helpers.id_utils import resolve_entity_by_id_variants
            main = await get_main_module()
            bot_client = main.bot_client
            
            target_entity, _ = await resolve_entity_by_id_variants(bot_client, target_chat_id_raw)
            if target_entity is None:
                # 回退到简单转换
                target_entity = int(str(target_chat_id_raw))
            return target_entity
        else:
            return fallback_chat_id
    
    @handle_errors(default_return=None)
    async def _schedule_message_deletion(self, message, delay_seconds):
        """
        安排消息删除
        
        Args:
            message: 要删除的消息
            delay_seconds: 延迟秒数
        """
        try:
            from services.task_service import message_task_manager
            await message_task_manager.schedule_delete(message, delay_seconds)
        except ImportError:
            # 兜底：使用原有方式
            import asyncio
            async def delete_after_delay():
                await asyncio.sleep(delay_seconds)
                try:
                    await message.delete()
                except Exception as e:
                    logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            
            # 异步执行撤回任务
            asyncio.create_task(delete_after_delay())
