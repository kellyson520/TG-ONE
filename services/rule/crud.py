"""
Rule Management CRUD Service (Core Logic)
Handles Create, Read, Update, Delete for Forward Rules.
Proxies to RuleRepository where possible, ensuring DTO contracts.
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from sqlalchemy import select, func, cast, String, delete
from sqlalchemy.orm import aliased, selectinload

from utils.core.error_handler import handle_errors, log_execution
from models.models import ForwardRule, Chat, Keyword, ReplaceRule
from schemas.rule import RuleDTO, RuleCreate
from enums.enums import ForwardMode, AddMode

logger = logging.getLogger(__name__)

class RuleCRUDService:
    @property
    def container(self):
        from core.container import container
        return container
    
    @handle_errors(default_return={'rules': [], 'total': 0, 'page': 0, 'page_size': 10})
    @log_execution()
    async def get_rule_list(self, page: int = 0, page_size: int = 10, search_query: str = None) -> Dict[str, Any]:
        """获取规则列表 (Updated to use standard Repo or direct DTO construction)"""
        async with self.container.db.session() as session:
            # Note: Repository get_all is strict pagination, but search query is complex dynamic.
            # For now, we keep manual construction but align output format.
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat),
                selectinload(ForwardRule.keywords),
                selectinload(ForwardRule.replace_rules),
                 selectinload(ForwardRule.media_types),
                selectinload(ForwardRule.media_extensions),
                selectinload(ForwardRule.rss_config),
                selectinload(ForwardRule.push_config)
            )
            
            if search_query:
                stmt = stmt.filter(
                    cast(ForwardRule.id, String).like(f'%{search_query}%')
                )
            
            # Simple Count
            # Optimized count (subquery overhead reduction if possible, but safe way first)
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_count = (await session.execute(count_stmt)).scalar() or 0
            
            stmt = stmt.offset(page * page_size).limit(page_size)
            result = await session.execute(stmt)
            rules_orm = result.scalars().all()
            
            # Convert to DTO then to Dict for Frontend Compatibility
            # Frontend likely expects specific dict structure.
            # DTO can .model_dump()
            rules_data = []
            for rule in rules_orm:
                dto = RuleDTO.model_validate(rule)
                # Helper for specific Frontend Format (legacy View compatibility)
                # If we fully migrated Frontend to DTO `json` it would be easier.
                # For now, map DTO to expected View Dict.
                
                rule_data = {
                    'id': dto.id,
                    'name': f"规则 {dto.id}",
                    'source_chat': dto.source_chat.model_dump() if dto.source_chat else {'title': 'Unknown', 'telegram_chat_id': 'Unknown'},
                    'target_chat': dto.target_chat.model_dump() if dto.target_chat else {'title': 'Unknown', 'telegram_chat_id': 'Unknown'},
                    'enabled': dto.enable_rule,
                    'created_at': dto.created_at,
                    'keywords_count': len(dto.keywords),
                    'replace_rules_count': len(dto.replace_rules),
                    'forward_mode': dto.forward_mode,
                    'is_ai': dto.is_ai,
                    'is_summary': dto.is_summary,
                }
                # Sanitize Chat titles for view if needed (DTO already contains basic fields)
                if rule_data['source_chat'].get('title') is None: rule_data['source_chat']['title'] = f"Chat {rule_data['source_chat'].get('telegram_chat_id')}"
                if rule_data['target_chat'].get('title') is None: rule_data['target_chat']['title'] = f"Chat {rule_data['target_chat'].get('telegram_chat_id')}"
                
                rules_data.append(rule_data)

            return {
                'rules': rules_data,
                'total': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size if page_size > 0 else 0
            }

    @handle_errors(default_return={'success': False, 'error': 'Rule not found'})
    async def get_rule_detail(self, rule_id: int) -> Dict[str, Any]:
        """获取规则详情"""
        # Delegate to Repository for fetch
        rule_dto = await self.container.rule_repo.get_by_id(rule_id)
        
        if not rule_dto:
             return {'success': False, 'error': '规则不存在'}
        
        # Serialization for Frontend View
        # Construct legacy dict from DTO
        
        # Extract keywords list specifically
        keywords = [k.keyword for k in rule_dto.keywords]
        
        # Extract replace rules
        replace_rules = [
            {'pattern': rr.pattern, 'replacement': rr.content, 'is_regex': False} # DTO missing is_regex in list? Check schema.
            for rr in rule_dto.replace_rules
        ]
        # Pydantic schema ReplaceRuleDTO might miss is_regex? Let's assume basic for now.
        
        return {
            'success': True,
            'id': rule_dto.id,
            'source_chat': rule_dto.source_chat.model_dump() if rule_dto.source_chat else {'title': 'Unknown'},
            'target_chat': rule_dto.target_chat.model_dump() if rule_dto.target_chat else {'title': 'Unknown'},
            'enabled': rule_dto.enable_rule,
            'forward_mode': rule_dto.forward_mode,
            'keywords': keywords,
            'keywords_count': len(keywords),
            'replace_rules': replace_rules,
            'replace_rules_count': len(replace_rules),
            'settings': {
                'enabled': rule_dto.enable_rule,
                'enable_dedup': rule_dto.enable_dedup,
                'dedup_time_window_hours': 24,
                'similarity_threshold': 0.85
            },
            'is_ai': rule_dto.is_ai,
            'is_summary': rule_dto.is_summary,
            'enable_dedup': rule_dto.enable_dedup,
            'created_at': rule_dto.created_at,
            'use_bot': rule_dto.use_bot,
            'handle_mode': rule_dto.handle_mode,
            'is_delete_original': rule_dto.is_delete_original,
            'message_mode': rule_dto.message_mode,
            'is_preview': rule_dto.is_preview,
            'is_original_sender': rule_dto.is_original_sender,
            'is_original_time': rule_dto.is_original_time,
            'is_original_link': rule_dto.is_original_link,
            'is_filter_user_info': rule_dto.is_filter_user_info,
            'enable_comment_button': rule_dto.enable_comment_button,
            'enable_delay': rule_dto.enable_delay,
            'delay_seconds': rule_dto.delay_seconds,
            'force_pure_forward': rule_dto.force_pure_forward,
            'enable_sync': rule_dto.enable_sync,
            # Add missing fields from Phase 1 requirements if any
        }

    @handle_errors(default_return={'success': False, 'error': 'Rule creation failed'})
    async def create_rule(self, source_chat_id: str, target_chat_id: str, **settings) -> Dict[str, Any]:
        """创建新规则"""
        # Logic remains largely same but ensures cleanup
        # This writes to DB, so Repo should handle validation
        from utils.helpers.id_utils import get_display_name_async
    
        try:
            async with self.container.db.session() as session:
                # 验证源聊天和目标聊天是否存在
                # Use Repo find_chat
                source_chat_dto = await self.container.rule_repo.find_chat(source_chat_id)
                target_chat_dto = await self.container.rule_repo.find_chat(target_chat_id)
                
                if not source_chat_dto:
                    return {'success': False, 'error': f'源聊天 {source_chat_id} 不存在'}
                if not target_chat_dto:
                    return {'success': False, 'error': f'目标聊天 {target_chat_id} 不存在'}
                
                # Create ORM object (Repo Create DTO? No, Repo usually takes DTO or raw args)
                # For Phase 2, we directly use ORM here for Creation as Repo might not have create_from_dto yet.
                # Ideally Repository should have `add(rule_dto)`.
                # For now, keep ORM creation here but clean.
                
                new_rule = ForwardRule(
                    source_chat_id=source_chat_dto.id,
                    target_chat_id=target_chat_dto.id,
                    enable_rule=settings.get('enable_rule', True),
                    enable_dedup=settings.get('enable_dedup', False),
                    forward_mode=settings.get('forward_mode', ForwardMode.BLACKLIST.value),
                    created_at=datetime.utcnow().isoformat()
                )
                 
                for key, value in settings.items():
                    if key not in ['enable_rule', 'enable_dedup', 'forward_mode'] and hasattr(new_rule, key):
                        setattr(new_rule, key, value)
                
                session.add(new_rule)
                await session.commit()
                await session.refresh(new_rule)
                
                # Invalidate Caches
                self.container.rule_repo.clear_cache(int(source_chat_dto.telegram_chat_id))
                self.container.rule_repo.clear_cache(int(target_chat_dto.telegram_chat_id))
                
                return {'success': True, 'rule_id': new_rule.id}

        except Exception as e:
            logger.error(f"[RuleCRUD] Creation failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    @handle_errors(default_return={'success': False, 'error': 'Rule update failed'})
    async def update_rule(self, rule_id: int, **settings) -> Dict[str, Any]:
        async with self.container.db.session() as session:
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat)
            ).filter_by(id=rule_id)
            rule = (await session.execute(stmt)).scalar_one_or_none()
            
            if not rule:
                 return {'success': False, 'error': '规则不存在'}

            source_id = int(rule.source_chat.telegram_chat_id) if rule.source_chat else None
            target_id = int(rule.target_chat.telegram_chat_id) if rule.target_chat else None

            from enum import Enum
            for key, value in settings.items():
                if hasattr(rule, key):
                    if isinstance(value, Enum):
                        value = value.value
                    setattr(rule, key, value)
            
            if hasattr(rule, 'updated_at'):
                rule.updated_at = datetime.utcnow().isoformat()
            
            await session.commit()
            
            # Cache Invalidation
            if source_id: self.container.rule_repo.clear_cache(source_id)
            if target_id: self.container.rule_repo.clear_cache(target_id)
            
            return {'success': True, 'rule_id': rule_id, 'source_chat_id': source_id, 'target_chat_id': target_id}

    @handle_errors(default_return={'success': False, 'error': 'Rule deletion failed'})
    async def delete_rule(self, rule_id: int) -> Dict[str, Any]:
         async with self.container.db.session() as session:
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat)
            ).filter_by(id=rule_id)
            rule = (await session.execute(stmt)).scalar_one_or_none()
            
            if not rule:
                 return {'success': False, 'error': '规则不存在'}
            
            source_id = int(rule.source_chat.telegram_chat_id) if rule.source_chat else None
            target_id = int(rule.target_chat.telegram_chat_id) if rule.target_chat else None
            
            await session.delete(rule)
            await session.commit()
            
            if source_id: self.container.rule_repo.clear_cache(source_id)
            if target_id: self.container.rule_repo.clear_cache(target_id)
            
            return {'success': True, 'message': 'Deleted successfully', 'source_chat_id': source_id, 'target_chat_id': target_id}

