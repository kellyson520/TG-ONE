import logging
from filters.base_filter import BaseFilter

logger = logging.getLogger(__name__)

class DeleteOriginalFilter(BaseFilter):
    """
    删除原始消息过滤器，处理转发后是否要删除原始消息
    """
    
    async def _process(self, context):
        """
        处理是否删除原始消息
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        rule = context.rule
        event = context.event
        
        # 如果不需要删除原始消息，直接返回
        if not rule.is_delete_original:
            return True
            
        try:
            # [Refactoring Note]
            # 避免在 Filter 阶段直接删除，防止后续转发逻辑（尤其是 Forward Mode）因消息丢失而失败。
            # 改为在 Context 中打标记，由后续中间件（如 CleanupMiddleware）或 Sender 发送成功后处理。
            
            logger.info(f"[Rule {rule.id}] Marking message {event.message.id} (Group: {event.message.grouped_id}) for later deletion.")
            
            # 标记需要删除
            if not hasattr(context, 'metadata'):
                context.metadata = {}
                
            context.metadata['delete_source_message'] = True
            
            # 如果是媒体组，记录 grouped_id 以便整体删除
            if event.message.grouped_id:
                context.metadata['delete_group_id'] = str(event.message.grouped_id)

            return True
        except Exception as e:
            logger.error(f'标记删除原始消息时出错: {str(e)}')
            context.errors.append(f"标记删除原始消息错误: {str(e)}")
            return True 
