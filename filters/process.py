import logging
from filters.factory import get_filter_chain_factory

logger = logging.getLogger(__name__)

async def process_forward_rule(client, event, chat_id, rule):
    """
    处理转发规则 - 使用配置化过滤器链
    
    Args:
        client: 机器人客户端
        event: 消息事件
        chat_id: 聊天ID
        rule: 转发规则
        
    Returns:
        bool: 处理是否成功
    """
    logger.info(f'使用配置化过滤器链处理规则 ID: {rule.id}')
    
    try:
        # 使用工厂创建过滤器链
        factory = get_filter_chain_factory()
        filter_chain = factory.create_chain_for_rule(rule, use_cache=True)
        
        # 执行过滤器链
        result = await filter_chain.process(client, event, chat_id, rule)
        
        logger.info(f'规则 {rule.id} 过滤器链处理完成，结果: {result}')
        return result
        
    except Exception as e:
        logger.error(f'规则 {rule.id} 过滤器链处理异常: {str(e)}', exc_info=True)
        return False 
