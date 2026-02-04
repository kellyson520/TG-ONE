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


        # 智能去重检查：使用新的智能去重系统
        if getattr(rule, 'enable_dedup', False):
            is_duplicate = await self._check_smart_duplicate(context, rule)
            if is_duplicate:
                # 处理重复消息删除
                await self._handle_duplicate_message_deletion(context, rule)
                context.should_forward = False
                return False

        # 支持复合条件：若规则启用了 sender 过滤，则必须同时满足
        # 约定：rule 可带属性 required_sender_id（字符串或整数），required_sender_regex（名称匹配）
        sender_ok = True
        try:
            required_sender = getattr(rule, 'required_sender_id', None)
            required_sender_regex = getattr(rule, 'required_sender_regex', None)
            if required_sender is not None or required_sender_regex:
                sender_id_val = getattr(context, 'sender_id', None)
                sender_name_val = getattr(context, 'sender_name', '') or ''
                if required_sender is not None:
                    try:
                        sender_ok = str(sender_id_val) == str(required_sender)
                    except Exception:
                        sender_ok = False
                if sender_ok and required_sender_regex:
                    import re as _re
                    try:
                        sender_ok = bool(_re.search(required_sender_regex, sender_name_val))
                    except Exception:
                        sender_ok = False
        except Exception:
            sender_ok = True

        # 增强关键词检查：支持API优化搜索
        keyword_ok = await self._enhanced_keyword_check(rule, message_text, event)
        should_forward = (sender_ok and keyword_ok)
        
        return should_forward
    
    async def _enhanced_keyword_check(self, rule, message_text, event):
        """
        增强的关键词检查，支持API优化搜索
        
        Args:
            rule: 转发规则
            message_text: 消息文本
            event: 消息事件
            
        Returns:
            bool: 是否通过关键词检查
        """
        from services.rule.filter import RuleFilterService
        try:
            # 优先使用 Service 进行基本检查
            basic_result = await RuleFilterService.check_keywords(rule, message_text, event)
            
            # 如果启用了搜索优化且有特殊需求，使用API搜索
            if hasattr(rule, 'enable_search_optimization') and rule.enable_search_optimization:
                return await self._optimized_keyword_search(rule, message_text, event, basic_result)
            
            return basic_result
            
        except Exception as e:
            logger.error(f"增强关键词检查失败: {str(e)}")
            # 回退到基本检查
            return await RuleFilterService.check_keywords(rule, message_text, event)
    
    async def _optimized_keyword_search(self, rule, message_text, event, basic_result):
        """
        使用API优化的关键词搜索
        
        Args:
            rule: 转发规则
            message_text: 消息文本
            event: 消息事件
            basic_result: 基本检查结果
            
        Returns:
            bool: 优化后的检查结果
        """
        try:
            # 如果基本检查已经通过，直接返回
            if basic_result:
                return True
            
            # 获取用户客户端
            try:
                main = await get_main_module()
                client = main.user_client
            except Exception:
                logger.warning("无法获取用户客户端，使用基本结果")
                return basic_result
            
            # 获取规则的关键词
            keywords = getattr(rule, 'keywords', [])
            if not keywords:
                return basic_result
            
            # 对于某些特殊场景，使用API搜索验证
            # 例如：检查相似消息是否在历史中存在
            chat_id = event.chat_id
            
            # 搜索最近的相关消息
            for keyword_obj in keywords[:3]:  # 限制搜索数量
                keyword_text = getattr(keyword_obj, 'keyword', '') if hasattr(keyword_obj, 'keyword') else str(keyword_obj)
                if not keyword_text:
                    continue
                
                # 使用API搜索
                search_results = await api_optimizer.search_messages_by_keyword(
                    client, chat_id, keyword_text, limit=10
                )
                
                if search_results:
                    logger.info(f"API搜索找到 {len(search_results)} 条相关消息，关键词: {keyword_text}")
                    # 如果找到了相关消息，说明该关键词在上下文中确实存在，通过检查
                    return True
            
            return basic_result
            
        except Exception as e:
            logger.error(f"API优化搜索失败: {str(e)}")
            return basic_result
    
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
        
        # 智能去重配置
        rule_config = {
            'enable_time_window': getattr(rule, 'enable_time_window_dedup', True),
            'time_window_hours': getattr(rule, 'dedup_time_window_hours', 24),
            'similarity_threshold': getattr(rule, 'similarity_threshold', 0.85),
            'enable_content_hash': getattr(rule, 'enable_content_hash_dedup', True),
            'enable_smart_similarity': getattr(rule, 'enable_smart_similarity', True),
        }
        
        target_chat_id = int(rule.target_chat.telegram_chat_id)
        is_duplicate, reason = await smart_deduplicator.check_duplicate(
            context.event.message, target_chat_id, rule_config
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
