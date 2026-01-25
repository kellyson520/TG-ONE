from sqlalchemy import select, or_, func, desc
from sqlalchemy.orm import selectinload
from models.models import ForwardRule, ForwardMapping, Chat
from utils.helpers.id_utils import build_candidate_telegram_ids
from utils.db.persistent_cache import get_persistent_cache, dumps_json, loads_json
import logging

logger = logging.getLogger(__name__)

from utils.processing.wtinylfu import WTinyLFU

# [Optimization] 使用 W-TinyLFU 替代标准 TTLCache 以提高热点规则命中率
class WTinyLFUCompatible(WTinyLFU):
    def __init__(self, ttl_seconds, maxsize):
        super().__init__(max_size=maxsize, ttl=ttl_seconds)

class RuleRepository:
    def __init__(self, db):
        self.db = db
        # 统一使用 W-TinyLFU 替代 TTLCache
        self._source_rules_cache = WTinyLFUCompatible(ttl_seconds=15, maxsize=1024)
        self._target_rules_cache = WTinyLFUCompatible(ttl_seconds=15, maxsize=1024)

    @staticmethod
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

    async def find_chat(self, chat_id):
        """根据telegram_chat_id查找聊天"""
        async with self.db.session() as session:
            # 尝试直接匹配
            stmt = select(Chat).filter(Chat.telegram_chat_id == str(chat_id))
            result = await session.execute(stmt)
            chat = result.scalar_one_or_none()
            if chat:
                logger.debug(f"✅ [find_chat] 直接匹配成功: {chat_id} -> Chat(id={chat.id}, name={chat.name})")
                return chat
            
            # 尝试变体匹配
            candidates = build_candidate_telegram_ids(chat_id)
            logger.debug(f"🔍 [find_chat] 直接匹配失败,尝试候选ID匹配: {chat_id} -> 候选集合={candidates}")
            
            if candidates:
                stmt = select(Chat).filter(Chat.telegram_chat_id.in_(list(candidates)))
                result = await session.execute(stmt)
                matched_chat = result.scalars().first()
                
                if matched_chat:
                    logger.info(f"✅ [find_chat] 候选ID匹配成功: {chat_id} -> Chat(id={matched_chat.id}, tg_id={matched_chat.telegram_chat_id}, name={matched_chat.name})")
                else:
                    logger.debug(f"❌ [find_chat] 所有候选ID均未匹配: {chat_id}, 候选={candidates}")
                
                return matched_chat
            return None

    async def get_by_id(self, rule_id: int):
        """根据ID获取规则，包含所有关联数据"""
        async with self.db.session() as session:
            stmt = (
                select(ForwardRule)
                .options(*self._get_rule_select_options())
                .where(ForwardRule.id == rule_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_rules_for_source_chat(self, chat_id):
        """获取源聊天的规则 (Unified Source of Truth)"""
        # 1. 查内存缓存 (TTLCache)
        cached = self._source_rules_cache.get(chat_id)
        if cached is not None:
            return cached

        # 2. 查持久化缓存 (Redis/File)
        try:
            pc = get_persistent_cache()
            raw = pc.get(f"rules:source:{chat_id}")
            if raw:
                ids = loads_json(raw) or []
                if ids:
                    async with self.db.session() as session:
                        stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter(ForwardRule.id.in_(ids))
                        result = await session.execute(stmt)
                        rules = result.scalars().all()
                        self._source_rules_cache[chat_id] = rules
                        return rules
        except Exception:
            pass

        # 3. 查数据库 (完整逻辑)
        async with self.db.session() as session:
            logger.debug(f"🔍 [get_rules_for_source_chat] 开始查询规则: chat_id={chat_id}")
            source_chat = await self.find_chat(chat_id)
            
            rules = []
            if not source_chat:
                logger.debug(f"⚠️ [get_rules_for_source_chat] 未找到聊天ID {chat_id} 对应的源聊天记录，尝试使用候选ID集合进行回退匹配")
                # 全量查询后内存过滤
                stmt = select(ForwardRule).options(*self._get_rule_select_options())
                result = await session.execute(stmt)
                all_rules = result.scalars().all()
                
                candidates = build_candidate_telegram_ids(chat_id)
                logger.debug(f"🔍 [get_rules_for_source_chat] 候选ID集合: {candidates}")
                
                for r in all_rules:
                    if not r.enable_rule:
                        continue
                    s_tid = getattr(r.source_chat, 'telegram_chat_id', None) if r.source_chat else None
                    if s_tid and s_tid in candidates:
                        logger.debug(f"✅ [get_rules_for_source_chat] 回退匹配成功: Rule#{r.id}, source_tg_id={s_tid}")
                        rules.append(r)
            else:
                logger.debug(f"✅ [get_rules_for_source_chat] 找到源聊天: Chat(id={source_chat.id}, tg_id={source_chat.telegram_chat_id}, name={source_chat.name})")
                # 优先查找多对多映射
                stmt = select(ForwardMapping).filter(
                    ForwardMapping.source_chat_id == source_chat.id,
                    ForwardMapping.enabled == True
                )
                result = await session.execute(stmt)
                mappings = result.scalars().all()
                
                if mappings:
                    for m in mappings:
                        if m.rule_id:
                            stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter_by(id=m.rule_id)
                            result = await session.execute(stmt)
                            rule = result.scalar_one_or_none()
                            if rule:
                                rules.append(rule)
                        else:
                            stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter(
                                ForwardRule.source_chat_id == source_chat.id,
                                ForwardRule.target_chat_id == m.target_chat_id
                            )
                            result = await session.execute(stmt)
                            rule = result.scalars().first()
                            if rule:
                                rules.append(rule)
                else:
                    # 使用旧架构查找转发规则
                    stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter(
                        ForwardRule.source_chat_id == source_chat.id
                    )
                    result = await session.execute(stmt)
                    rules = result.scalars().all()
        
        # 4. 写缓存 (Both Layers)
        self._source_rules_cache[chat_id] = rules
        try:
            pc = get_persistent_cache()
            pc.set(f"rules:source:{chat_id}", dumps_json([r.id for r in rules]), ttl=30)
        except Exception:
            pass
        
        return rules

    def clear_cache(self, chat_id: int = None):
        """清理缓存 (Unified)
        
        Args:
            chat_id: 如果指定，仅清理特定聊天的缓存；否则清理所有
        """
        try:
            # 清理持久化缓存
            pc = get_persistent_cache()
            if chat_id:
                # 内存缓存
                if chat_id in self._source_rules_cache:
                    del self._source_rules_cache[chat_id]
                if chat_id in self._target_rules_cache:
                    del self._target_rules_cache[chat_id]
                
                # 持久化缓存
                pc.delete(f"rules:source:{chat_id}")
                pc.delete(f"rules:target:{chat_id}")
            else:
                # 内存缓存
                self._source_rules_cache.clear()
                self._target_rules_cache.clear()
                # 持久化缓存清理比较复杂，通常 relying on TTL is fine or specific key deletion
        except Exception as e:
            logger.warning(f"Failed to clear cache: {e}")

    async def get_rules_for_target_chat(self, chat_id):
        """获取目标聊天的规则 (Unified Source of Truth)"""
        # 1. 查内存缓存
        cached = self._target_rules_cache.get(chat_id)
        if cached is not None:
            return cached

        # 2. 查持久化缓存
        try:
            pc = get_persistent_cache()
            raw = pc.get(f"rules:target:{chat_id}")
            if raw:
                ids = loads_json(raw) or []
                if ids:
                    async with self.db.session() as session:
                        stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter(ForwardRule.id.in_(ids))
                        result = await session.execute(stmt)
                        rules = result.scalars().all()
                        self._target_rules_cache[chat_id] = rules
                        return rules
        except Exception:
            pass

        # 3. 查数据库
        async with self.db.session() as session:
            target_chat = await self.find_chat(chat_id)
            
            if not target_chat:
                rules = []
            else:
                stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter(
                    ForwardRule.target_chat_id == target_chat.id
                )
                result = await session.execute(stmt)
                rules = result.scalars().all()
            
        # 4. 写缓存
        self._target_rules_cache[chat_id] = rules
        try:
            pc = get_persistent_cache()
            pc.set(f"rules:target:{chat_id}", dumps_json([r.id for r in rules]), ttl=30)
        except Exception:
            pass
            
        return rules

    async def get_all_rules_with_chats(self):
        """获取所有规则，包括关联的聊天"""
        async with self.db.session() as session:
            stmt = select(ForwardRule).options(*self._get_rule_select_options())
            result = await session.execute(stmt)
            rules = result.scalars().all()
            return rules

    async def get_rules_related_to_chat(self, chat_id):
        """获取与聊天相关的规则"""
        async with self.db.session() as session:
            candidate_tg_ids = build_candidate_telegram_ids(chat_id)
            candidate_list = list(candidate_tg_ids)

            stmt = select(Chat).filter(Chat.telegram_chat_id.in_(candidate_list))
            result = await session.execute(stmt)
            internal_row = result.scalars().first()
            internal_id = internal_row.id if internal_row else None

            if internal_id is not None:
                stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter(
                    or_(ForwardRule.source_chat_id == internal_id,
                        ForwardRule.target_chat_id == internal_id)
                ).order_by(ForwardRule.id)
                result = await session.execute(stmt)
                rules = result.scalars().all()
            else:
                # 内存过滤 (回退)
                stmt = select(ForwardRule).options(*self._get_rule_select_options()).order_by(ForwardRule.id)
                result = await session.execute(stmt)
                all_rules = result.scalars().all()
                rules = []
                for r in all_rules:
                    s_tid = getattr(r.source_chat, 'telegram_chat_id', None) if r.source_chat else None
                    t_tid = getattr(r.target_chat, 'telegram_chat_id', None) if r.target_chat else None
                    if (s_tid and s_tid in candidate_tg_ids) or (t_tid and t_tid in candidate_tg_ids):
                        rules.append(r)

            return rules

    async def get_all(self, page: int = 1, size: int = 50):
        """标准分页查询，替代 Web Admin 中的手写 SQL"""
        async with self.db.session() as session:
            # 1. 获取总数
            count_stmt = select(func.count(ForwardRule.id))
            total = (await session.execute(count_stmt)).scalar() or 0

            # 2. 获取数据 (带预加载)
            stmt = (
                select(ForwardRule)
                .options(*self._get_rule_select_options())
                .order_by(ForwardRule.id.desc()) # 默认倒序
                .offset((page - 1) * size)
                .limit(size)
            )
            result = await session.execute(stmt)
            items = result.scalars().all()
            
            return items, total

    async def toggle_rule(self, rule_id: int) -> bool:
        """切换规则开关"""
        async with self.db.session() as session:
            stmt = select(ForwardRule).filter_by(id=rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            if rule:
                rule.enable_rule = not rule.enable_rule
                await session.commit()
                # 清除缓存，确保下次获取最新数据
                self.clear_cache()
                return rule.enable_rule
            return None

    async def get_all_chats(self):
        """获取所有聊天列表"""
        async with self.db.session() as session:
            stmt = select(Chat).order_by(Chat.id.asc())
            result = await session.execute(stmt)
            chats = result.scalars().all()
            return chats