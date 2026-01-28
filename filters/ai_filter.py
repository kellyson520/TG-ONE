
import logging
from filters.base_filter import BaseFilter
from core.helpers.common import check_keywords

logger = logging.getLogger(__name__)

class AIFilter(BaseFilter):
    """
    AI处理过滤器 (重构版)
    逻辑已委托给 services.media_service 和 services.ai_service
    """
    
    async def _process(self, context):
        rule = context.rule
        if not rule.is_ai:
            return True

        try:
            from services.media_service import ai_media_processor
            from services.ai_service import ai_service

            image_files = []
            
            # 1. 收集媒体 (优先使用已下载文件，其次直接下载到内存)
            if rule.enable_ai_upload_image:
                if context.media_files:
                    for f in context.media_files:
                        data = await ai_media_processor.load_file_to_memory(f)
                        if data: image_files.append(data)
                elif context.is_media_group and getattr(context, 'media_group_messages', None):
                    for msg in context.media_group_messages:
                        if getattr(msg, 'photo', None) or (getattr(msg, 'document', None) and msg.document.mime_type.startswith('image/')):
                            data = await ai_media_processor.download_message_media_to_memory(msg)
                            if data: image_files.append(data)
                elif context.event.message and getattr(context.event.message, 'media', None):
                     data = await ai_media_processor.download_message_media_to_memory(context.event.message)
                     if data: image_files.append(data)

            # 2. 执行 AI 处理
            if context.message_text or image_files:
                processed_text = await ai_service.process_message(
                    text=context.message_text or "[图片消息]",
                    rule=rule,
                    images=image_files,
                    context=context 
                )
                
                context.message_text = processed_text

            # 3. 后置关键词重新检查
            if rule.is_keyword_after_ai:
                if not await check_keywords(rule, context.message_text, context.event):
                    context.should_forward = False
                    return False

        except Exception as e:
            logger.error(f"AI Filter Error: {e}", exc_info=True)
            context.errors.append(f"AI Error: {e}")
            
        return True
