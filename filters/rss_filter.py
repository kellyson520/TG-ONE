import logging
from filters.base_filter import BaseFilter
from filters.base_filter import BaseFilter
from core.constants import RSS_ENABLED

logger = logging.getLogger(__name__)

class RSSFilter(BaseFilter):
    """
    RSS过滤器 (重构版)
    逻辑已委托给 services.rss_service.RssService
    """
    
    async def _process(self, context):
        """处理RSS过滤器逻辑"""
        from services.rss_service import rss_service
        
        if not RSS_ENABLED:
            logger.debug("RSS未启用，跳过RSS处理")
            return True
        
        if not context.should_forward:
            return False
        
        try:
            # 执行RSS业务逻辑
            if context.is_media_group:
                # 假设 context.media_group_messages 存在
                messages = getattr(context, 'media_group_messages', [])
                if messages:
                    await rss_service.process_media_group_rss(context.client, messages, context.rule, context)
            else:
                await rss_service.process_rss_item(
                    context.client, 
                    context.event.message, 
                    context.rule, 
                    context
                )
                
        except Exception as e:
            logger.error(f"RSS Filter 执行失败: {e}", exc_info=True)
            # RSS 失败不应阻断主流程，除非 only_rss 被设置
            
        # 如果设置了只转发到RSS，则停止后续转发流程
        if context.rule.only_rss:
            logger.info('只转发到RSS，RSS过滤器已完成，结束过滤链')
            return False
        
        return True
