"""
Rule Core - DI setup, rule copy, chat binding, statistics, and cleanup.
"""
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from core.helpers.error_handler import handle_errors
from enums.enums import ForwardMode

logger = logging.getLogger(__name__)


class RuleCoreMixin:
    """Core operations: DI injection, copy, bind, stats, cleanup."""

    def __init__(self):
        self._db = None
        self._rule_repo = None
        self._bus = None
        self._scheduler = None

    def set_db(self, db):
        self._db = db

    def set_rule_repo(self, rule_repo):
        self._rule_repo = rule_repo

    def set_bus(self, bus):
        self._bus = bus

    def set_scheduler(self, scheduler):
        self._scheduler = scheduler

    @handle_errors(default_return={'success': False, 'error': 'Rule copy failed'})
    async def copy_rule(self, source_rule_id: int, target_rule_id: Optional[int] = None) -> Dict[str, Any]:
        if not target_rule_id:
             return {'success': False, 'error': 'Target Rule ID required'}

        source_rule = await self._rule_repo.get_full_rule_orm(source_rule_id)
        if not source_rule:
            return {'success': False, 'error': f'Source rule {source_rule_id} not found'}

        target_rule = await self._rule_repo.get_full_rule_orm(target_rule_id)
        if not target_rule:
            return {'success': False, 'error': f'Target rule {target_rule_id} not found'}

        exclude_cols = {'id', 'source_chat_id', 'target_chat_id', 'created_at', 'updated_at'}
        for column in source_rule.__table__.columns:
            if column.name not in exclude_cols:
                setattr(target_rule, column.name, getattr(source_rule, column.name))

        target_rule.keywords.clear()
        from models.models import Keyword, ReplaceRule, MediaExtensions, MediaTypes, RuleSync
        for kw in source_rule.keywords:
            target_rule.keywords.append(Keyword(
                keyword=kw.keyword, is_regex=kw.is_regex, is_blacklist=kw.is_blacklist
            ))

        target_rule.replace_rules.clear()
        for rr in source_rule.replace_rules:
            target_rule.replace_rules.append(ReplaceRule(
                pattern=rr.pattern, content=rr.content
            ))

        target_rule.media_extensions.clear()
        for ext in source_rule.media_extensions:
            target_rule.media_extensions.append(MediaExtensions(extension=ext.extension))

        if source_rule.media_types:
            if not target_rule.media_types:
                target_rule.media_types = MediaTypes()

            from sqlalchemy import inspect
            media_inspector = inspect(MediaTypes)
            for column in media_inspector.columns:
                if column.key not in ["id", "rule_id"]:
                     setattr(target_rule.media_types, column.key, getattr(source_rule.media_types, column.key))

        target_rule.rule_syncs.clear()
        for sync in source_rule.rule_syncs:
            if sync.sync_rule_id != target_rule.id:
                target_rule.rule_syncs.append(RuleSync(sync_rule_id=sync.sync_rule_id))

        source_chat_id = int(target_rule.source_chat.telegram_chat_id) if target_rule.source_chat else None
        await self._rule_repo.save_rule(target_rule)

        if source_chat_id:
            self._rule_repo.clear_cache(source_chat_id)

        return {'success': True, 'message': 'Rule copied successfully'}

    @handle_errors(default_return={'success': False, 'error': 'Chat binding failed'})
    async def bind_chat(self, client, source_input: str, target_input: Optional[str] = None, current_chat_id: Optional[int] = None) -> Dict[str, Any]:
        from core.helpers.id_utils import get_or_create_chat_async

        target_name, target_tid, target_chat_obj = await get_or_create_chat_async(client, target_input)
        if not target_chat_obj:
             return {'success': False, 'error': f'无法识别目标聊天: {target_input}'}

        source_chat_name, source_chat_id, source_chat_obj = await get_or_create_chat_async(client, source_input)
        if not source_chat_id:
             return {'success': False, 'error': f'无法获取源聊天信息: {source_input}'}

        existing_rule = await self._rule_repo.get_rule_by_source_target(source_chat_obj.id, target_chat_obj.id)

        is_new = False
        if not existing_rule:
            new_rule = await self._rule_repo.create_rule(
                source_chat_id=source_chat_obj.id,
                target_chat_id=target_chat_obj.id,
                enable_rule=True,
                forward_mode=ForwardMode.BLACKLIST,
                created_at=datetime.utcnow()
            )
            is_new = True
            rule_id = new_rule.id
        else:
            rule_id = existing_rule.id

        self._rule_repo.clear_cache(int(source_chat_id))

        return {
            'success': True,
            'is_new': is_new,
            'rule_id': rule_id,
            'source_name': source_chat_name,
            'target_name': target_name
        }

    @handle_errors(default_return={'success': False, 'error': 'Clear all data failed'})
    async def clear_all_data(self) -> Dict[str, Any]:
        count = await self._rule_repo.delete_all_rules()
        self._rule_repo.clear_cache()
        return {'success': True, 'message': f'所有规则数据已清空 (影响 {count} 条)'}

    async def get_rule_statistics(self) -> Dict[str, Any]:
        count = await self._rule_repo.get_rule_count()
        return {'total_rules': count}

    async def cleanup_orphan_chats(self, rule_deleted=None) -> int:
        chat_ids_to_check = []
        if rule_deleted:
            if hasattr(rule_deleted, 'source_chat_id') and rule_deleted.source_chat_id:
                chat_ids_to_check.append(rule_deleted.source_chat_id)
            if hasattr(rule_deleted, 'target_chat_id') and rule_deleted.target_chat_id:
                chat_ids_to_check.append(rule_deleted.target_chat_id)
        else:
            chat_ids_to_check = await self._rule_repo.get_all_chat_ids()

        orphan_ids = []
        for chat_id in chat_ids_to_check:
            refs = await self._rule_repo.count_rule_refs_for_chat(chat_id)
            if refs['as_source'] == 0 and refs['as_target'] == 0:
                chat_dto = await self._rule_repo.find_chat_by_id_internal(chat_id)
                if chat_dto:
                    affected_chats = await self._rule_repo.get_chats_using_add_id(chat_dto.telegram_chat_id)
                    for other in affected_chats:
                        await self._rule_repo.update_chat_current_add_id(other.id, None)
                    orphan_ids.append(chat_id)

        if orphan_ids:
            return await self._rule_repo.delete_orphan_chats(orphan_ids)
        return 0

    @handle_errors(default_return={'success': False, 'error': 'Immediate summary task failed'})
    async def summary_now(self, rule_id: int) -> Dict[str, Any]:
        rule_dto = await self._rule_repo.get_by_id(rule_id)
        if not rule_dto:
            return {'success': False, 'error': 'Rule not found'}

        if not self._scheduler:
            return {'success': False, 'error': 'Scheduler not initialized'}

        # 启动异步任务
