import logging
from filters.base_filter import BaseFilter
from repositories.db_context import async_safe_db_operation

logger = logging.getLogger(__name__)

class SenderFilter(BaseFilter):
    """
    消息发送过滤器
    
    职责：
    1. 验证转发规则是否满足基本条件 (should_forward)。
    2. 验证目标聊天 (Target Chat) 是否有效及可用。
    3. 解析目标 ID 并预存至上下文，供下游 SenderMiddleware 使用。
    
    注意：本过滤器严格遵守“单一职责”原则，只做准入判定，不执行任何发送动作。
    实际的发送逻辑由 middlewares/sender.py 统一处理。
    """
    
    async def _process(self, context):
        """
        验证发送条件和目标有效性
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 
                - True: 规则有效，允许进入发送队列（由 SenderMiddleware 执行发送）。
                - False: 规则无效或条件不满足，拦截处理。
        """
        rule = context.rule
        client = context.client
        
        # 1. 基础转发条件检查
        if not context.should_forward:
            logger.info(f'[SenderFilter] 规则 {rule.id} 不满足转发条件，跳过判定')
            return False
        
        # 2. 如果是“仅推送”模式，直接放行
        # 注意：SenderMiddleware 需要自行处理 enable_only_push 逻辑，或者由 PushMiddleware 处理
        if getattr(rule, 'enable_only_push', False):
            logger.info(f'[SenderFilter] 规则 {rule.id} 配置为“仅推送”，通过准入判定')
            return True
            
        # 3. 获取目标聊天信息
        target_chat = getattr(rule, 'target_chat', None)
        if target_chat is None:
            # 兼容性处理：尝试从数据库补全信息
            target_chat = await self._get_target_chat(rule)

        if not target_chat:
            logger.error(f'[SenderFilter] 规则 {rule.id} 无法确定目标聊天，准入判定失败')
            return False

        # 4. 验证并解析目标 ID
        # 这一步是为了确保目标频道/群组在 Telethon 缓存中存在，或提前发现无效 ID
        from core.helpers.id_utils import resolve_entity_by_id_variants
        target_chat_id = int(target_chat.telegram_chat_id)
        
        try:
            # 尝试解析实体，验证机器人是否仍在群组中/频道是否有效
            entity, resolved_id = await resolve_entity_by_id_variants(client, target_chat_id)
            
            final_id = resolved_id if resolved_id is not None else target_chat_id
            
            # 将解析后的 ID 注入 metadata，供 Middleware 使用（避免重复解析）
            # Key 格式保障规则级别的隔离
            context.metadata[f'resolved_target_id_{rule.id}'] = final_id
            
            if entity:
                logger.debug(f'[SenderFilter] 规则 {rule.id} 目标验证成功: {target_chat.name} (ID: {final_id})')
            else:
                logger.info(f'[SenderFilter] 规则 {rule.id} 目标实体未缓存，尝试使用原始 ID: {final_id}')
                
        except Exception as e:
            # 即使校验失败，通常也记录警告并放行，让发送器在最后时刻尝试（可能由网络波动导致解析失败）
            logger.warning(f'[SenderFilter] 验证目标聊天实体时出错 (规则 {rule.id}): {str(e)}')
        
        # 5. 准入通过
        # 此时不执行发送，Pipeline 会继续流转到 SenderMiddleware
        return True

    @async_safe_db_operation
    async def _get_target_chat(self, rule):
        """
        数据库操作：获取 Chat 模型对象
        """
        from models.models import Chat
        target_chat_id = getattr(rule, 'target_chat_id', None)
        
        # 内部函数用于在 session 上下文中执行
        async def _op(session):
            if target_chat_id:
                return await session.get(Chat, target_chat_id)
            return None
            
        return await _op(None) # session 由装饰器自动注入