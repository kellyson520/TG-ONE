"""转发规则查询服务模块 (原生异步版)"""

from __future__ import annotations
import logging
from typing import List, Optional, Any, Tuple, Dict
from schemas.rule import RuleDTO
from schemas.chat import ChatDTO

logger = logging.getLogger(__name__)

class RuleQueryService:
    """转发规则查询服务 (Proxy to RuleRepository)"""
    
    def __init__(self):
        self._rule_repo = None
        self._db = None

    def set_repos(self, rule_repo, db):
        """注入仓储依赖 (由 Container 调用，打破循环依赖)"""
        self._rule_repo = rule_repo
        self._db = db

    async def get_rules_for_source_chat(self, chat_id: int) -> List[RuleDTO]:
        """获取源聊天的转发规则"""
        logger.info(f"🔍 [规则服务] 获取源聊天规则: 聊天ID={chat_id}")
        rules = await self._rule_repo.get_rules_for_source_chat(chat_id)
        logger.info(f"✅ [规则服务] 获取源聊天规则完成: 聊天ID={chat_id}, 规则数量={len(rules)}")
        return rules

    async def get_rules_for_target_chat(self, chat_id: int) -> List[RuleDTO]:
        """获取目标聊天的转发规则"""
        logger.info(f"🔍 [规则服务] 获取目标聊天规则: 聊天ID={chat_id}")
        rules = await self._rule_repo.get_rules_for_target_chat(chat_id)
        logger.info(f"✅ [规则服务] 获取目标聊天规则完成: 聊天ID={chat_id}, 规则数量={len(rules)}")
        return rules

    def invalidate_caches_for_chat(self, chat_id: int) -> None:
        """失效聊天缓存"""
        logger.info(f"🔄 [规则服务] 失效聊天缓存: 聊天ID={chat_id}")
        self._rule_repo.clear_cache(chat_id)

    def invalidate_all_caches(self) -> None:
        """失效所有缓存"""
        logger.info(f"🔄 [规则服务] 失效所有缓存")
        self._rule_repo.clear_cache()

    async def get_current_rule_for_chat(self, event: Any, session: Any = None) -> Optional[Tuple[RuleDTO, ChatDTO]]:
        """获取当前聊天的当前选中规则"""
        async def _logic(_sess):
            try:
                current_chat = await event.get_chat()
                current_chat_db = await self._rule_repo.find_chat(current_chat.id)

                if not current_chat_db or not current_chat_db.current_add_id:
                    return None

                source_chat = await self._rule_repo.find_chat(current_chat_db.current_add_id)
                if not source_chat:
                    return None

                rule = await self._rule_repo.get_rule_by_source_target(source_chat.id, current_chat_db.id)
                return (rule, source_chat) if rule else None
                
            except Exception as e:
                logger.error(f'获取当前规则时出错: {str(e)}', exc_info=True)
                return None

        if session:
            return await _logic(session)
        else:
            async with self._db.get_session() as session:
                return await _logic(session)

    async def get_all_rules_with_chats(self) -> List[RuleDTO]:
        """获取所有转发规则"""
        try:
            return await self._rule_repo.get_all_rules_with_chats()
        except Exception as e:
            logger.error(f"获取所有转发规则失败: {str(e)}", exc_info=True)
            return []

    async def get_all_chats(self) -> List[ChatDTO]:
        """获取所有聊天列表"""
        try:
            return await self._rule_repo.get_all_chats()
        except Exception as e:
            logger.error(f"获取所有聊天列表失败: {str(e)}", exc_info=True)
            return []

    async def get_visualization_data(self) -> Dict[str, Any]:
        """
        获取规则-聊天图谱数据
        用于前端 ECharts/G6 展示
        """
        try:
            rules = await self._rule_repo.get_all_rules_with_chats()
            chats = await self._rule_repo.get_all_chats()
            
            nodes = []
            links = []
            
            # 1. 节点: 聊天
            chat_map = {}
            for chat in chats:
                display_name = chat.title or chat.name or f"Chat {chat.telegram_chat_id}"
                chat_map[chat.id] = display_name
                nodes.append({
                    "id": str(chat.id),
                    "name": display_name,
                    "category": chat.type if hasattr(chat, 'type') else "unknown",
                    "value": str(chat.telegram_chat_id)
                })
            
            # 2. 连线: 规则 (Source -> Target)
            for rule in rules:
                if rule.source_chat_id and rule.target_chat_id:
                    links.append({
                        "id": str(rule.id),
                        "source": str(rule.source_chat_id),
                        "target": str(rule.target_chat_id),
                        "label": "Rule #" + str(rule.id),
                        "active": rule.enable_rule
                    })
            
            return {
                "nodes": nodes,
                "links": links
            }
        except Exception as e:
            logger.error(f"获取可视化数据失败: {str(e)}", exc_info=True)
            return {"nodes": [], "links": []}

    async def get_rules_related_to_chat(self, chat_id: int) -> List[RuleDTO]:
        """获取聊天相关规则"""
        try:
            return await self._rule_repo.get_rules_related_to_chat(chat_id)
        except Exception as e:
            logger.error(f"获取聊天相关规则失败: {str(e)}", exc_info=True)
            return []
