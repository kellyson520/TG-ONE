import logging 
from filters.base_filter import BaseFilter 
from filters.context import MessageContext 
from models.models import MediaSignature 
from repositories.db_context import async_db_session

logger = logging.getLogger(__name__)

class FilterChain:
    """
    过滤器链，用于组织和执行多个过滤器
    """
    
    def __init__(self):
        """初始化过滤器链"""
        self.filters = []
        
    def add_filter(self, filter_obj):
        """
        添加过滤器到链中
        
        Args:
            filter_obj: 要添加的过滤器对象，必须是BaseFilter的子类
        """
        if not isinstance(filter_obj, BaseFilter):
            raise TypeError("过滤器必须是BaseFilter的子类")
        self.filters.append(filter_obj)
        return self
        
    async def process(self, client, event, chat_id, rule):
        """
        处理消息 (Legacy helper, creates internal context)
        """
        context = MessageContext(client, event, chat_id, rule)
        return await self.process_context(context)

    async def process_context(self, context: MessageContext) -> bool:
        """
        处理消息上下文
        
        Args:
            context: 已初始化的消息上下文
            
        Returns:
            bool: 是否需继续后续流程 (Success)
        """
        logger.info(f"开始过滤器链处理，共 {len(self.filters)} 个过滤器 (TraceID: {getattr(context, 'trace_id', 'N/A')})")
        
        import asyncio
        for filter_obj in self.filters:
            try:
                should_continue = await asyncio.wait_for(
                    filter_obj.process(context),
                    timeout=10.0
                )
                if not should_continue:
                    logger.info(f"过滤器 {filter_obj.name} 中断了处理链")
                    return False
            except asyncio.TimeoutError:
                logger.error(f"过滤器 {filter_obj.name} 执行超时（10秒），中断处理")
                context.errors.append(f"过滤器 {filter_obj.name} 执行超时")
                return False
            except Exception as e:
                logger.error(f"过滤器 {filter_obj.name} 处理出错: {str(e)}")
                context.errors.append(f"过滤器 {filter_obj.name} 错误: {str(e)}")
                return False
                
        return True
        
        # 过滤链全部通过后，若已实际发送，记录媒体签名（用于后续去重，计数累加）
        try:
            if getattr(context, 'forwarded_messages', None) and hasattr(context, 'dup_signatures') and context.dup_signatures:
                from repositories.db_operations import DBOperations
                async with async_db_session() as session:
                    try:
                        db_ops = await DBOperations.create()
                        if context.rule and context.rule.target_chat:
                            target_chat_id = str(context.rule.target_chat.telegram_chat_id)
                            for sig, mid in context.dup_signatures:
                                await db_ops.add_media_signature(session, target_chat_id, sig, mid)
                    except Exception as inner_e:
                         logger.warning(f"添加媒体签名数据库操作失败: {str(inner_e)}")
        except Exception as e:
            logger.warning(f"记录媒体签名失败: {str(e)}")

        logger.info("过滤器链处理完成")
        return True 
