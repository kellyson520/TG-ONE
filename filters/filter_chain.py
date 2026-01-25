import logging 
from filters.base_filter import BaseFilter 
from filters.context import MessageContext 
from models.models import MediaSignature 
from utils.db.db_context import async_db_session

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
        处理消息
        
        Args:
            client: 机器人客户端
            event: 消息事件
            chat_id: 聊天ID
            rule: 转发规则
            
        Returns:
            bool: 表示处理是否成功
        """
        # 创建消息上下文
        context = MessageContext(client, event, chat_id, rule)
        
        logger.info(f"开始过滤器链处理，共 {len(self.filters)} 个过滤器")
        
        import asyncio
        # 依次执行每个过滤器，设置超时机制防止阻塞
        for filter_obj in self.filters:
            try:
                # 为每个过滤器设置10秒超时
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
        
        # 过滤链全部通过后，若已实际发送，记录媒体签名（用于后续去重，计数累加）
        try:
            if getattr(context, 'forwarded_messages', None) and hasattr(context, 'dup_signatures') and context.dup_signatures:
                from utils.db.db_operations import DBOperations
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
