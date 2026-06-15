"""
Rule Settings - Toggle settings, AI model, media types/extensions, sync, and scheduling.
"""
from typing import Dict, Any, Optional
import logging

from core.helpers.error_handler import handle_errors

logger = logging.getLogger(__name__)


class RuleSettingsMixin:
    """Rule settings and synchronization operations."""

    @handle_errors(default_return={'success': False, 'error': 'Update summary time failed'})
    async def update_summary_time(self, rule_id: int, time: str) -> Dict[str, Any]:
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select
        from core.helpers.common import get_main_module

        async with self._db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule: return {'success': False, 'error': 'Rule not found'}

            rule.summary_time = time

            if rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    target = await s.get(ForwardRule, sync_obj.sync_rule_id)
                    if target:
                        target.summary_time = time
                        if target.is_summary:
                            main = await get_main_module()
                            if main.scheduler: await main.scheduler.schedule_rule(target)

            await s.commit()

            if rule.is_summary:
                main = await get_main_module()
                if main.scheduler: await main.scheduler.schedule_rule(rule)

            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Update AI model failed'})
    async def update_ai_model(self, rule_id: int, model: str) -> Dict[str, Any]:
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule: return {'success': False, 'error': 'Rule not found'}

            rule.ai_model = model

            if rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    target = await s.get(ForwardRule, sync_obj.sync_rule_id)
                    if target: target.ai_model = model

            await s.commit()
            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Toggle setting failed'})
    async def toggle_rule_setting(self, rule_id: int, field: str, value: Optional[Any] = None) -> Dict[str, Any]:
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule: return {'success': False, 'error': 'Rule not found'}
            if not hasattr(rule, field):
                return {'success': False, 'error': f'Invalid field: {field}'}

            current_val = getattr(rule, field)
            if value is None:
                if not isinstance(current_val, bool):
                    return {'success': False, 'error': f'Field is not toggleable without value: {field}'}
                new_val = not current_val
            else:
                new_val = value

            setattr(rule, field, new_val)

            if rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    target = await s.get(ForwardRule, sync_obj.sync_rule_id)
                    if target and hasattr(target, field):
                        setattr(target, field, new_val)

            await s.commit()
            self._rule_repo.clear_cache()
            bus = self._bus
            if bus:
                await bus.publish("RULE_UPDATED", {"rule_id": int(rule_id), "field": field, "action": "update"})

            return {'success': True, 'new_value': new_val}

    @handle_errors(default_return={'success': False, 'error': 'Toggle media type failed'})
    async def toggle_media_type(self, rule_id: int, media_type: str) -> Dict[str, Any]:
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule: return {'success': False, 'error': 'Rule not found'}

            success, msg = await self._rule_repo.toggle_media_type(s, rule.id, media_type)
            if not success: return {'success': False, 'error': msg}

            _, _, media_types_obj = await self._rule_repo.get_media_types(s, rule.id)
            new_status = getattr(media_types_obj, media_type)

            if rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                results = await s.execute(sync_stmt)
                for sync_obj in results.scalars().all():
                    await self._rule_repo.set_media_type_status(s, sync_obj.sync_rule_id, media_type, new_status)

            await s.commit()
            return {'success': True, 'new_status': new_status}

    @handle_errors(default_return={'success': False, 'error': 'Toggle media extension failed'})
    async def toggle_media_extension(self, rule_id: int, extension: str) -> Dict[str, Any]:
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule: return {'success': False, 'error': 'Rule not found'}

            exts = await self._rule_repo.get_media_extensions(s, rule.id)
            is_selected = any(e['extension'] == extension for e in exts)

            if is_selected:
                ext_id = next((e['id'] for e in exts if e['extension'] == extension), None)
                if ext_id:
                    success, msg = await self._rule_repo.delete_media_extensions(s, rule.id, [ext_id])
                else:
                    success, msg = True, "Already removed"
            else:
                success, msg = await self._rule_repo.add_media_extensions(s, rule.id, [extension])

            if not success: return {'success': False, 'error': msg}

            if rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                results = await s.execute(sync_stmt)
                for sync_obj in results.scalars().all():
                    if is_selected:
                        await self._rule_repo.remove_extension_from_rule(s, sync_obj.sync_rule_id, extension)
                    else:
                        await self._rule_repo.add_media_extensions(s, sync_obj.sync_rule_id, [extension])

            await s.commit()
            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Toggle rule sync failed'})
    async def toggle_rule_sync(self, source_rule_id: int, target_rule_id: int) -> Dict[str, Any]:
        from models.models import RuleSync
        from sqlalchemy import select, delete

        async with self._db.get_session() as s:
            stmt = select(RuleSync).filter_by(rule_id=source_rule_id, sync_rule_id=target_rule_id)
            existing = (await s.execute(stmt)).scalar_one_or_none()

            if existing:
                await s.delete(existing)
                action = "removed"
            else:
                new_sync = RuleSync(rule_id=source_rule_id, sync_rule_id=target_rule_id)
                s.add(new_sync)
                action = "added"

            await s.commit()
            return {'success': True, 'action': action}

    @handle_errors(default_return={'success': False, 'error': 'Setting current source chat failed'})
    async def set_current_source_chat(self, chat_id: int, source_telegram_id: str) -> Dict[str, Any]:
        from models.models import Chat
        async with self._db.get_session() as s:
            chat = await s.get(Chat, chat_id)
            if not chat:
                return {'success': False, 'error': 'Chat not found'}

            chat.current_add_id = source_telegram_id
            await s.commit()
            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Updating AI setting failed'})
    async def update_ai_setting(self, rule_id: int, field: str, value: Any) -> Dict[str, Any]:
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule:
                return {'success': False, 'error': 'Rule not found'}
            if not hasattr(rule, field):
                return {'success': False, 'error': f'Invalid field: {field}'}

            old_val = getattr(rule, field)
            setattr(rule, field, value)

            rules_to_reschedule = [rule.id] if rule.is_summary and field == 'summary_time' else []

            if rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                sync_results = await s.execute(sync_stmt)
                for sync_obj in sync_results.scalars().all():
                    target = await s.get(ForwardRule, sync_obj.sync_rule_id)
                    if target and hasattr(target, field):
                        setattr(target, field, value)
                        if target.is_summary and field == 'summary_time':
                            rules_to_reschedule.append(target.id)

            await s.commit()
            self._rule_repo.clear_cache()
            bus = self._bus
            if bus:
                await bus.publish("RULE_UPDATED", {"rule_id": int(rule_id), "field": field, "action": "update"})

            scheduler = self._scheduler
            if rules_to_reschedule and scheduler:
                for rid in rules_to_reschedule:
                    latest_rule_dto = await self._rule_repo.get_by_id(rid)
                    if latest_rule_dto:
                         await scheduler.schedule_rule(latest_rule_dto)

            return {'success': True, 'old_value': old_val, 'new_value': value}
