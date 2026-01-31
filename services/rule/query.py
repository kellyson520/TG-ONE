"""转发规则查询服务模块 (原生异步版)"""

from __future__ import annotations
import logging
from typing import List, Optional, Any, Tuple
from schemas.rule import RuleDTO
from schemas.chat import ChatDTO

logger = logging.getLogger(__name__)

class RuleQueryService:
    """转发规则查询服务 (Proxy to RuleRepository)"""
    
    @staticmethod
    async def get_rules_for_source_chat(chat_id: int) -> List[RuleDTO]:
        """获取源聊天的转发规则"""
        logger.info(f"🔍 [规则服务] 获取源聊天规则: 聊天ID={chat_id}")
        from core.container import container
        rules = await container.rule_repo.get_rules_for_source_chat(chat_id)
        logger.info(f"✅ [规则服务] 获取源聊天规则完成: 聊天ID={chat_id}, 规则数量={len(rules)}")
        return rules

    @staticmethod
    async def get_rules_for_target_chat(chat_id: int) -> List[RuleDTO]:
        """获取目标聊天的转发规则"""
        logger.info(f"🔍 [规则服务] 获取目标聊天规则: 聊天ID={chat_id}")
        from core.container import container
        rules = await container.rule_repo.get_rules_for_target_chat(chat_id)
        logger.info(f"✅ [规则服务] 获取目标聊天规则完成: 聊天ID={chat_id}, 规则数量={len(rules)}")
        return rules

    @staticmethod
    def invalidate_caches_for_chat(chat_id: int) -> None:
        """失效聊天缓存"""
        logger.info(f"🔄 [规则服务] 失效聊天缓存: 聊天ID={chat_id}")
        from core.container import container
        container.rule_repo.clear_cache(chat_id)

    @staticmethod
    def invalidate_all_caches() -> None:
        """失效所有缓存"""
        logger.info(f"🔄 [规则服务] 失效所有缓存")
        from core.container import container
        container.rule_repo.clear_cache()

    @staticmethod
    async def get_current_rule_for_chat(event: Any, session: Any = None) -> Optional[Tuple[RuleDTO, ChatDTO]]:
        """获取当前聊天的当前选中规则"""
        from core.container import container
        
        async def _logic(_sess):
            try:
                current_chat = await event.get_chat()
                current_chat_db = await container.rule_repo.find_chat(current_chat.id)

                if not current_chat_db or not current_chat_db.current_add_id:
                    return None

                source_chat = await container.rule_repo.find_chat(current_chat_db.current_add_id)
                if not source_chat:
                    return None

                rule = await container.rule_repo.get_rule_by_source_target(source_chat.id, current_chat_db.id)
                return (rule, source_chat) if rule else None
                
            except Exception as e:
                logger.error(f'获取当前规则时出错: {str(e)}', exc_info=True)
                return None

        if session:
            return await _logic(session)
        else:
            async with container.db.session() as session:
                return await _logic(session)

    @staticmethod
    async def get_all_rules_with_chats() -> List[RuleDTO]:
        """获取所有转发规则"""
        try:
            from core.container import container
            return await container.rule_repo.get_all_rules_with_chats()
        except Exception as e:
            logger.error(f"获取所有转发规则失败: {str(e)}", exc_info=True)
            return []

    @staticmethod 
    async def get_rules_related_to_chat(chat_id: int) -> List[RuleDTO]:
        """获取聊天相关规则"""
        try:
            from core.container import container
            return await container.rule_repo.get_rules_related_to_chat(chat_id)
        except Exception as e:
            logger.error(f"获取聊天相关规则失败: {str(e)}", exc_info=True)
            return []
