"""转发规则查询服务模块 (原生异步版)"""

from __future__ import annotations
import logging
from typing import List, Optional, Any, Tuple
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from models.models import ForwardRule, ForwardMapping, Chat
# [Refactor Fix] 更新为使用 container (移至内部以避免循环导入)
# from core.container import container
# [Refactor Fix] 更新 id_utils 路径
from utils.helpers.id_utils import build_candidate_telegram_ids
# [Refactor Fix] 替换 utils.cache
from utils.db.persistent_cache import get_persistent_cache, dumps_json, loads_json

try:
    from cachetools import TTLCache
except ImportError:
    # 简单的内存缓存回退实现
    class TTLCache(dict):
        def __init__(self, ttl_seconds, maxsize):
            super().__init__()
            self.ttl = ttl_seconds
            self.maxsize = maxsize

logger = logging.getLogger(__name__)


def _get_rule_select_options():
    """获取ForwardRule查询的预加载选项"""
    return [
        selectinload(ForwardRule.source_chat),
        selectinload(ForwardRule.target_chat),
        selectinload(ForwardRule.keywords),
        selectinload(ForwardRule.replace_rules),
        selectinload(ForwardRule.media_types),
        selectinload(ForwardRule.media_extensions),
        selectinload(ForwardRule.rss_config),
        selectinload(ForwardRule.push_config)
    ]


async def _find_chat_async(session, chat_id):
    """异步查找聊天"""
    # 尝试直接匹配
    stmt = select(Chat).filter(Chat.telegram_chat_id == str(chat_id))
    result = await session.execute(stmt)
    chat = result.scalar_one_or_none()
    if chat:
        return chat
    
    # 尝试变体匹配
    candidates = build_candidate_telegram_ids(chat_id)
    if candidates:
        stmt = select(Chat).filter(Chat.telegram_chat_id.in_(list(candidates)))
        result = await session.execute(stmt)
        return result.scalars().first()
    return None


class RuleQueryService:
    """转发规则查询服务 (Proxy to RuleRepository)"""
    
    @staticmethod
    async def get_rules_for_source_chat(chat_id: int) -> List[ForwardRule]:
        """获取源聊天的转发规则"""
        logger.info(f"🔍 [规则服务] 获取源聊天规则: 聊天ID={chat_id}")
        from core.container import container
        rules = await container.rule_repo.get_rules_for_source_chat(chat_id)
        logger.info(f"✅ [规则服务] 获取源聊天规则完成: 聊天ID={chat_id}, 规则数量={len(rules)}")
        return rules

    @staticmethod
    async def get_rules_for_target_chat(chat_id: int) -> List[ForwardRule]:
        """获取目标聊天的转发规则"""
        logger.info(f"🔍 [规则服务] 获取目标聊天规则: 聊天ID={chat_id}")
        from core.container import container
        rules = await container.rule_repo.get_rules_for_target_chat(chat_id)
        logger.info(f"✅ [规则服务] 获取目标聊天规则完成: 聊天ID={chat_id}, 规则数量={len(rules)}")
        return rules

    @staticmethod
    def invalidate_caches_for_chat(chat_id: int) -> None:
        """Call repository to clear cache"""
        logger.info(f"🔄 [规则服务] 失效聊天缓存: 聊天ID={chat_id}")
        from core.container import container
        container.rule_repo.clear_cache(chat_id)
        logger.info(f"✅ [规则服务] 聊天缓存失效完成: 聊天ID={chat_id}")

    @staticmethod
    def invalidate_all_caches() -> None:
        """Clear all repository caches"""
        logger.info(f"🔄 [规则服务] 失效所有缓存")
        from core.container import container
        container.rule_repo.clear_cache()
        logger.info(f"✅ [规则服务] 所有缓存失效完成")

    @staticmethod
    async def get_current_rule_for_chat(event: Any, session: Any) -> Optional[Tuple[ForwardRule, Chat]]:
        """获取当前聊天的当前选中规则 (session应为异步session)"""
        try:
            current_chat = await event.get_chat()
            current_chat_db = await _find_chat_async(session, current_chat.id)

            if not current_chat_db or not current_chat_db.current_add_id:
                return None

            source_chat = await _find_chat_async(session, current_chat_db.current_add_id)
            if not source_chat:
                return None

            stmt = select(ForwardRule).filter(
                ForwardRule.source_chat_id == source_chat.id,
                ForwardRule.target_chat_id == current_chat_db.id
            )
            result = await session.execute(stmt)
            rule = result.scalars().first()

            if not rule:
                return None

            return rule, source_chat
            
        except Exception as e:
            logger.error(f'获取当前规则时出错: {str(e)}', exc_info=True)
            return None

    @staticmethod
    async def get_all_rules_with_chats() -> List[ForwardRule]:
        try:
            from core.container import container
            async with container.db.session() as session:
                stmt = select(ForwardRule).options(*_get_rule_select_options())
                result = await session.execute(stmt)
                rules = result.scalars().all()
                return rules
        except Exception as e:
            logger.error(f"获取所有转发规则失败: {str(e)}", exc_info=True)
            return []

    @staticmethod 
    async def get_rules_related_to_chat(chat_id: int) -> List[ForwardRule]:
        try:
            from core.container import container
            async with container.db.session() as session:
                candidate_tg_ids = build_candidate_telegram_ids(chat_id)
                candidate_list = list(candidate_tg_ids)

                stmt = select(Chat).filter(Chat.telegram_chat_id.in_(candidate_list))
                result = await session.execute(stmt)
                internal_row = result.scalars().first()
                internal_id = internal_row.id if internal_row else None

                if internal_id is not None:
                    stmt = select(ForwardRule).options(*_get_rule_select_options()).filter(
                        or_(ForwardRule.source_chat_id == internal_id,
                            ForwardRule.target_chat_id == internal_id)
                    ).order_by(ForwardRule.id)
                    result = await session.execute(stmt)
                    rules = result.scalars().all()
                else:
                    # 内存过滤 (回退)
                    stmt = select(ForwardRule).options(*_get_rule_select_options()).order_by(ForwardRule.id)
                    result = await session.execute(stmt)
                    all_rules = result.scalars().all()
                    rules = []
                    for r in all_rules:
                        s_tid = getattr(r.source_chat, 'telegram_chat_id', None) if r.source_chat else None
                        t_tid = getattr(r.target_chat, 'telegram_chat_id', None) if r.target_chat else None
                        if (s_tid and s_tid in candidate_tg_ids) or (t_tid and t_tid in candidate_tg_ids):
                            rules.append(r)

                return rules
        except Exception as e:
            logger.error(f"获取聊天相关规则失败: {str(e)}", exc_info=True)
            return []
