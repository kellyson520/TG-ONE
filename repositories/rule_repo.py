from typing import List, Optional, Any, Dict
import logging
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from models.models import ForwardRule, ForwardMapping, Chat
from core.helpers.id_utils import build_candidate_telegram_ids
from core.cache.persistent_cache import get_persistent_cache, dumps_json, loads_json
from schemas.rule import RuleDTO
from schemas.chat import ChatDTO
from core.helpers.db_utils import retry_on_db_lock
logger = logging.getLogger(__name__)

from core.cache.wtinylfu import WTinyLFU

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

    async def find_chat(self, chat_id) -> ChatDTO:
        """根据telegram_chat_id查找聊天"""
        async with self.db.session() as session:
            # 尝试直接匹配
            stmt = select(Chat).filter_by(telegram_chat_id=str(chat_id))
            chat = (await session.execute(stmt)).scalars().first()
            if chat:
                logger.debug(f"✅ [find_chat] 直接匹配成功: {chat_id}")
                return ChatDTO.model_validate(chat)
            
            # 尝试变体匹配
            candidates = build_candidate_telegram_ids(chat_id)
            
            if candidates:
                stmt = select(Chat).filter(Chat.telegram_chat_id.in_(list(candidates)))
                result = await session.execute(stmt)
                matched_chat = result.scalars().first()
                
                if matched_chat:
                    logger.info(f"✅ [find_chat] 候选ID匹配成功: {chat_id} -> {matched_chat.telegram_chat_id}")
                    return ChatDTO.model_validate(matched_chat)
                
                return None
            return None

    async def find_chat_by_id_internal(self, chat_id: int) -> Optional[ChatDTO]:
        """根据数据库自增ID查找聊天 (Internal View)"""
        async with self.db.session() as session:
            chat = await session.get(Chat, chat_id)
            return ChatDTO.model_validate(chat) if chat else None

    async def get_by_id(self, rule_id: int) -> RuleDTO:
        """根据ID获取规则，包含所有关联数据"""
        async with self.db.session() as session:
            stmt = (
                select(ForwardRule)
                .options(*self._get_rule_select_options())
                .where(ForwardRule.id == rule_id)
            )
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
            return RuleDTO.model_validate(obj) if obj else None

    async def get_rules_for_source_chat(self, chat_id) -> List[RuleDTO]:
        """获取源聊天的规则 (Unified Source of Truth)"""
        # 1. 查内存缓存 (TTLCache)
        cached = self._source_rules_cache.get(chat_id)
        if cached is not None:
            return cached

        # 2. 查持久化缓存
        try:
            pc = get_persistent_cache()
            raw = pc.get(f"rules:source:{chat_id}")
            if raw:
                ids = loads_json(raw) or []
                if ids:
                    async with self.db.session() as session:
                        stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter(ForwardRule.id.in_(ids))
                        result = await session.execute(stmt)
                        orm_rules = result.scalars().all()
                        rules = [RuleDTO.model_validate(r) for r in orm_rules]
                        self._source_rules_cache[chat_id] = rules
                        return rules
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

        # 3. 查数据库
        async with self.db.session() as session:
            source_chat = await self.find_chat(chat_id)
            
            rules_orm = []
            if not source_chat:
                stmt = select(ForwardRule).options(*self._get_rule_select_options())
                result = await session.execute(stmt)
                all_rules = result.scalars().all()
                candidates = build_candidate_telegram_ids(chat_id)
                for r in all_rules:
                    if not r.enable_rule: continue
                    s_tid = getattr(r.source_chat, 'telegram_chat_id', None) if r.source_chat else None
                    if s_tid and s_tid in candidates:
                        rules_orm.append(r)
            else:
                stmt = select(ForwardMapping).filter(ForwardMapping.source_chat_id == source_chat.id, ForwardMapping.enabled == True)
                mappings = (await session.execute(stmt)).scalars().all()
                if mappings:
                    # 批量获取 rule_id 列表
                    rule_ids = [m.rule_id for m in mappings if m.rule_id]
                    if rule_ids:
                        stmt_batch = select(ForwardRule).options(*self._get_rule_select_options()).where(ForwardRule.id.in_(rule_ids))
                        res_batch = await session.execute(stmt_batch)
                        rules_orm.extend(res_batch.scalars().all())
                    
                    # 对于没有 rule_id 的 mapping，保持原样（通常这种情况很少）
                    for m in mappings:
                        if not m.rule_id:
                            stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter_by(source_chat_id=source_chat.id, target_chat_id=m.target_chat_id)
                            r = (await session.execute(stmt)).scalars().first()
                            if r: rules_orm.append(r)
                else:
                    stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter_by(source_chat_id=source_chat.id)
                    rules_orm = (await session.execute(stmt)).scalars().all()
        
        rules = [RuleDTO.model_validate(r) for r in rules_orm]
        self._source_rules_cache[chat_id] = rules
        try:
            pc = get_persistent_cache()
            pc.set(f"rules:source:{chat_id}", dumps_json([r.id for r in rules]), ttl=30)
        except Exception as e:
            logger.debug(f"Failed to update persistent cache: {e}")
        return rules

    def clear_cache(self, chat_id: int = None):
        """清理缓存"""
        try:
            pc = get_persistent_cache()
            if chat_id:
                if chat_id in self._source_rules_cache: del self._source_rules_cache[chat_id]
                if chat_id in self._target_rules_cache: del self._target_rules_cache[chat_id]
                pc.delete(f"rules:source:{chat_id}")
                pc.delete(f"rules:target:{chat_id}")
            else:
                self._source_rules_cache.clear()
                self._target_rules_cache.clear()
        except Exception as e:
            logger.debug(f"Failed to clear cache: {e}")

    async def get_rules_for_target_chat(self, chat_id) -> List[RuleDTO]:
        """获取目标聊天的规则"""
        cached = self._target_rules_cache.get(chat_id)
        if cached is not None: return cached
        try:
            pc = get_persistent_cache()
            raw = pc.get(f"rules:target:{chat_id}")
            if raw:
                ids = loads_json(raw) or []
                if ids:
                    async with self.db.session() as session:
                        stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter(ForwardRule.id.in_(ids))
                        orm_rules = (await session.execute(stmt)).scalars().all()
                        rules = [RuleDTO.model_validate(r) for r in orm_rules]
                        self._target_rules_cache[chat_id] = rules
                        return rules
        except Exception as e:
            logger.debug(f"Persistent cache error: {e}")

        async with self.db.session() as session:
            target_chat = await self.find_chat(chat_id)
            rules_orm = []
            if target_chat:
                stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter_by(target_chat_id=target_chat.id)
                rules_orm = (await session.execute(stmt)).scalars().all()
            rules = [RuleDTO.model_validate(r) for r in rules_orm]

        self._target_rules_cache[chat_id] = rules
        try:
            pc = get_persistent_cache()
            pc.set(f"rules:target:{chat_id}", dumps_json([r.id for r in rules]), ttl=30)
        except Exception as e:
            logger.debug(f"Failed to set persistent cache: {e}")
        return rules

    async def get_full_rule_orm(self, rule_id: int) -> Optional[ForwardRule]:
        """获取完整的ForwardRule ORM对象 (仅限Service内部使用)"""
        async with self.db.session() as session:
            stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter_by(id=rule_id)
            return (await session.execute(stmt)).scalar_one_or_none()

    async def get_rule_by_source_target(self, source_chat_id: int, target_chat_id: int) -> Optional[RuleDTO]:
        async with self.db.session() as session:
            stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter_by(source_chat_id=source_chat_id, target_chat_id=target_chat_id)
            obj = (await session.execute(stmt)).scalar_one_or_none()
            return RuleDTO.model_validate(obj) if obj else None

    @retry_on_db_lock(retries=5)
    async def create_rule(self, **kwargs) -> RuleDTO:
        """创建规则并返回 DTO"""
        from enum import Enum
        processed_kwargs = {}
        for k, v in kwargs.items():
            processed_kwargs[k] = v.value if isinstance(v, Enum) else v
            
        async with self.db.session() as session:
            rule = ForwardRule(**processed_kwargs)
            session.add(rule)
            await session.commit()
            await session.refresh(rule)
            # 重新加载以包含关联数据
            stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter_by(id=rule.id)
            obj = (await session.execute(stmt)).scalar_one()
            return RuleDTO.model_validate(obj)

    async def delete_all_rules(self) -> int:
        async with self.db.session() as session:
            stmt = delete(ForwardRule)
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount

    async def get_rule_count(self) -> int:
        async with self.db.session() as session:
            stmt = select(func.count(ForwardRule.id))
            return (await session.execute(stmt)).scalar() or 0

    @retry_on_db_lock(retries=5)
    async def save_rule(self, rule: ForwardRule) -> RuleDTO:
        """保存规则 ORM 并返回 DTO"""
        async with self.db.session() as session:
            rule = await session.merge(rule)
            await session.commit()
            await session.refresh(rule)
            # 重新加载以确保 DTO 验证通过
            stmt = select(ForwardRule).options(*self._get_rule_select_options()).filter_by(id=rule.id)
            obj = (await session.execute(stmt)).scalar_one()
            return RuleDTO.model_validate(obj)

    async def delete_orphan_chats(self, chat_ids: List[int]) -> int:
        async with self.db.session() as session:
            if not chat_ids:
                return 0
            stmt = delete(Chat).where(Chat.id.in_(chat_ids))
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def get_all_chat_ids(self) -> List[int]:
        async with self.db.session() as session:
            stmt = select(Chat.id)
            return [r[0] for r in (await session.execute(stmt)).all()]

    async def count_rule_refs_for_chat(self, chat_id: int) -> Dict[str, int]:
        async with self.db.session() as session:
            stmt_s = select(func.count(ForwardRule.id)).filter_by(source_chat_id=chat_id)
            stmt_t = select(func.count(ForwardRule.id)).filter_by(target_chat_id=chat_id)
            return {
                'as_source': (await session.execute(stmt_s)).scalar() or 0,
                'as_target': (await session.execute(stmt_t)).scalar() or 0
            }

    async def get_chats_using_add_id(self, tg_chat_id: str) -> List[ChatDTO]:
        async with self.db.session() as session:
            stmt = select(Chat).filter_by(current_add_id=tg_chat_id)
            return [ChatDTO.model_validate(c) for c in (await session.execute(stmt)).scalars().all()]

    async def get_all_rules_with_chats(self) -> List[RuleDTO]:
        """获取所有转发规则 (不分页)"""
        async with self.db.session() as session:
            stmt = (
                select(ForwardRule)
                .options(*self._get_rule_select_options())
                .order_by(ForwardRule.id.desc())
            )
            result = await session.execute(stmt)
            orm_rules = result.scalars().all()
            return [RuleDTO.model_validate(r) for r in orm_rules]

    async def get_rules_related_to_chat(self, chat_id: Any) -> List[RuleDTO]:
        """获取聊天相关规则 (作为源或目标)"""
        async with self.db.session() as session:
            # 兼容 telegram_chat_id 和 db_id
            chat = await self.find_chat(chat_id)
            if not chat:
                return []
                
            stmt = (
                select(ForwardRule)
                .filter(
                    (ForwardRule.source_chat_id == chat.id) | 
                    (ForwardRule.target_chat_id == chat.id)
                )
                .options(*self._get_rule_select_options())
                .order_by(ForwardRule.id.desc())
            )
            result = await session.execute(stmt)
            orm_rules = result.scalars().all()
            return [RuleDTO.model_validate(r) for r in orm_rules]

    async def get_all(self, page: int = 1, size: int = 10) -> Any:
        """分页获取所有规则"""
        async with self.db.session() as session:
            total_stmt = select(func.count(ForwardRule.id))
            total_res = await session.execute(total_stmt)
            total = total_res.scalar() or 0
            
            stmt = (
                select(ForwardRule)
                .options(*self._get_rule_select_options())
                .order_by(ForwardRule.id.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
            result = await session.execute(stmt)
            orm_rules = result.scalars().all()
            return [RuleDTO.model_validate(r) for r in orm_rules], total

    @retry_on_db_lock(retries=5)
    async def toggle_rule(self, rule_id: int) -> bool:
        """切换规则启用状态"""
        async with self.db.session() as session:
            rule = await session.get(ForwardRule, rule_id)
            if not rule:
                raise ValueError("Rule not found")
            rule.enable_rule = not rule.enable_rule
            new_status = rule.enable_rule
            await session.commit()
            self.clear_cache()
            return new_status

    async def update_chat_current_add_id(self, chat_id: int, add_id: Optional[str]):
        async with self.db.session() as session:
            chat = await session.get(Chat, chat_id)
            if chat:
                chat.current_add_id = add_id
                await session.commit()

    async def get_all_chats(self) -> List[ChatDTO]:
        async with self.db.session() as session:
            stmt = select(Chat).order_by(Chat.id.asc())
            return [ChatDTO.model_validate(c) for c in (await session.execute(stmt)).scalars().all()]

    async def get_priority_map(self) -> Dict[int, int]:
        """获取源聊天优先级映射 {telegram_chat_id(int): priority}"""
        try:
            pc = get_persistent_cache()
            raw = pc.get("rules:priority_map")
            if raw:
                data = loads_json(raw)
                return {int(k): v for k, v in data.items()}
        except Exception:
            pass
            
        priority_map = {}
        async with self.db.session() as session:
            # 1. Direct Rules
            stmt1 = (
                select(Chat.telegram_chat_id, ForwardRule.priority)
                .join(ForwardRule, ForwardRule.source_chat_id == Chat.id)
                .where(ForwardRule.enable_rule == True)
                .where(ForwardRule.priority > 0)
            )
            for row in (await session.execute(stmt1)):
                if row[0]: 
                    try:
                        key = int(row[0])
                        priority_map[key] = max(priority_map.get(key, 0), row[1])
                    except ValueError:
                        pass

            # 2. Mapped Rules
            stmt2 = (
                select(Chat.telegram_chat_id, ForwardRule.priority)
                .join(ForwardMapping, ForwardMapping.source_chat_id == Chat.id)
                .join(ForwardRule, ForwardMapping.rule_id == ForwardRule.id)
                .where(ForwardMapping.enabled == True)
                .where(ForwardRule.enable_rule == True)
                .where(ForwardRule.priority > 0)
            )
            for row in (await session.execute(stmt2)):
                 if row[0]:
                    try:
                        key = int(row[0])
                        priority_map[key] = max(priority_map.get(key, 0), row[1])
                    except ValueError:
                        pass
            
        try:
            pc.set("rules:priority_map", dumps_json(priority_map), ttl=60)
        except Exception:
            pass
            
        return priority_map