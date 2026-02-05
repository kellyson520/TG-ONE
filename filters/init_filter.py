import logging
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    pytz = None
    PYTZ_AVAILABLE = False

from filters.base_filter import BaseFilter

logger = logging.getLogger(__name__)

class InitFilter(BaseFilter):
    """
    初始化过滤器，为context添加基本信息
    """
    
    async def _process(self, context):
        """
        添加原始链接和发送者信息
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        rule = context.rule
        event = context.event

        # logger.info(f"InitFilter处理消息前，context: {context.__dict__}")
        try:
            # [Fix] 优化媒体组处理，防止 N+1 API 调用
            if event.message.grouped_id:
                from core.cache.unified_cache import get_smart_cache
                unified_cache = get_smart_cache("media_group")
                # [Fix] 增加 chat_id 以前缀，防止跨会话 grouped_id 碰撞
                cache_key = f"media_group_ctx:{event.chat_id}:{event.message.grouped_id}"
                
                # 尝试从缓存获取已拉取的上下文（有效期 30秒，足以覆盖一个媒体组的到达时间）
                cached_ctx = unified_cache.get(cache_key)
                if cached_ctx:
                    context.message_text = cached_ctx.get('text', '')
                    context.original_message_text = cached_ctx.get('text', '')
                    context.check_message_text = cached_ctx.get('text', '')
                    context.buttons = cached_ctx.get('buttons')
                    # logger.debug(f"从缓存复用媒体组上下文: {event.message.grouped_id}")
                else:
                    # 仅在缓存未命中的情况下执行 API 调用
                    try:
                        async for message in event.client.iter_messages(
                            event.chat_id,
                            limit=20,
                            min_id=event.message.id - 10,
                            max_id=event.message.id + 10
                        ):
                            if message.grouped_id == event.message.grouped_id:
                                if message.text:    
                                    # 保存第一条消息的文本和按钮
                                    context.message_text = message.text or ''
                                    context.original_message_text = message.text or ''
                                    context.check_message_text = message.text or ''
                                    context.buttons = message.buttons if hasattr(message, 'buttons') else None
                                    
                                    # 存入缓存供媒体组后续消息使用
                                    unified_cache.set(cache_key, {
                                        'text': message.text,
                                        'buttons': message.buttons if hasattr(message, 'buttons') else None
                                    }, ttl=30)
                                    break
                    except Exception as e:
                        logger.error(f'收集媒体组消息时出错: {str(e)}')
                        context.errors.append(f"收集媒体组消息错误: {str(e)}")

            # [Cleanup] 移除冗余的老旧去重签名逻辑，后续由 KeywordFilter 中的 smart_deduplicator 统一处理
            context.dup_signatures = []
           
        finally:
            # logger.info(f"InitFilter处理消息后，context: {context.__dict__}")
            return True
