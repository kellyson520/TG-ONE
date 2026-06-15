"""
Push Manager - Push config CRUD, toggle settings, sync push configurations.
"""
from typing import Dict, Any
import logging

from core.helpers.error_handler import handle_errors

logger = logging.getLogger(__name__)


class PushManagerMixin:
    """Push configuration operations for rule management."""

    @handle_errors(default_return={'success': False, 'error': 'Adding push config failed'})
    async def add_push_config(self, rule_id: int, push_channel: str) -> Dict[str, Any]:
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule:
                return {'success': False, 'error': 'Rule not found'}

            stmt = select(PushConfig).filter_by(rule_id=rule.id, push_channel=push_channel)
            existing = (await s.execute(stmt)).scalar_one_or_none()
            if existing:
                 return {'success': True, 'message': 'Push channel already exists'}

            is_email = push_channel.startswith(("mailto://", "mailtos://", "email://"))
            config = PushConfig(
                rule_id=rule.id,
                push_channel=push_channel,
                enable_push_channel=True,
                media_send_mode="Multiple" if is_email else "Single"
            )
            s.add(config)
            rule.enable_push = True

            if rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                sync_results = await s.execute(sync_stmt)
                for sync_obj in sync_results.scalars().all():
                     target = await s.get(ForwardRule, sync_obj.sync_rule_id)
                     if target:
                         t_stmt = select(PushConfig).filter_by(rule_id=target.id, push_channel=push_channel)
                         t_existing = (await s.execute(t_stmt)).scalar_one_or_none()
                         if not t_existing:
                             s.add(PushConfig(
                                 rule_id=target.id,
                                 push_channel=push_channel,
                                 enable_push_channel=True,
                                 media_send_mode=config.media_send_mode
                             ))
                             target.enable_push = True

            await s.commit()
            if rule.source_chat:
                self._rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))

            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Toggle push config setting failed'})
    async def toggle_push_config_setting(self, config_id: int, field: str) -> Dict[str, Any]:
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            config = await s.get(PushConfig, int(config_id))
            if not config: return {'success': False, 'error': 'Config not found'}
            if not hasattr(config, field):
                return {'success': False, 'error': f'Invalid field: {field}'}

            rule_id = config.rule_id
            push_channel = config.push_channel

            current_val = getattr(config, field)
            if not isinstance(current_val, bool):
                return {'success': False, 'error': f'Field is not toggleable: {field}'}
            new_val = not current_val
            setattr(config, field, new_val)

            rule = await s.get(ForwardRule, rule_id)
            if rule and rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    stmt = select(PushConfig).filter_by(rule_id=sync_obj.sync_rule_id, push_channel=push_channel)
                    target_config = (await s.execute(stmt)).scalar_one_or_none()
                    if target_config:
                        setattr(target_config, field, new_val)

            await s.commit()
            self._rule_repo.clear_cache()
            bus = self._bus
            if bus:
                await bus.publish("RULE_UPDATED", {"rule_id": int(rule_id), "field": field, "action": "update"})
            return {'success': True, 'new_value': new_val}

    @handle_errors(default_return={'success': False, 'error': 'Toggle media send mode failed'})
    async def toggle_media_send_mode(self, config_id: int) -> Dict[str, Any]:
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            config = await s.get(PushConfig, int(config_id))
            if not config:
                return {'success': False, 'error': 'Config not found'}

            new_mode = "Multiple" if config.media_send_mode == "Single" else "Single"
            config.media_send_mode = new_mode

            rule = await s.get(ForwardRule, config.rule_id)
            if rule and rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    stmt = select(PushConfig).filter_by(rule_id=sync_obj.sync_rule_id, push_channel=config.push_channel)
                    target_config = (await s.execute(stmt)).scalar_one_or_none()
                    if target_config:
                        target_config.media_send_mode = new_mode

            await s.commit()
            return {'success': True, 'new_mode': new_mode}

    @handle_errors(default_return={'success': False, 'error': 'Toggle push config status failed'})
    async def toggle_push_status_by_config(self, config_id: int) -> Dict[str, Any]:
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            config = await s.get(PushConfig, int(config_id))
            if not config: return {'success': False, 'error': 'PushConfig not found'}

            config.enable_push_channel = not config.enable_push_channel
            new_status = config.enable_push_channel
            push_channel = config.push_channel

            rule = await s.get(ForwardRule, config.rule_id)
            if rule and rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                results = await s.execute(sync_stmt)
                for sync_obj in results.scalars().all():
                    target_config_stmt = select(PushConfig).filter_by(rule_id=sync_obj.sync_rule_id, push_channel=push_channel)
                    target_config = (await s.execute(target_config_stmt)).scalar_one_or_none()
                    if target_config:
                        target_config.enable_push_channel = new_status

            await s.commit()
            return {'success': True, 'new_value': new_status}

    @handle_errors(default_return={'success': False, 'error': 'Delete push config failed'})
    async def delete_push_config(self, config_id: int) -> Dict[str, Any]:
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            config = await s.get(PushConfig, int(config_id))
            if not config: return {'success': False, 'error': 'PushConfig not found'}

            rule_id = config.rule_id
            push_channel = config.push_channel

            rule = await s.get(ForwardRule, rule_id)
            if rule and rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                results = await s.execute(sync_stmt)
                for sync_obj in results.scalars().all():
                    target_config_stmt = select(PushConfig).filter_by(rule_id=sync_obj.sync_rule_id, push_channel=push_channel)
                    target_config = (await s.execute(target_config_stmt)).scalar_one_or_none()
                    if target_config:
                        await s.delete(target_config)

            await s.delete(config)
            await s.commit()
            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Update push config setting failed'})
    async def update_push_config_setting(self, config_id: int, field: str, value: Any) -> Dict[str, Any]:
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select

        async with self._db.get_session() as s:
            config = await s.get(PushConfig, int(config_id))
            if not config: return {'success': False, 'error': 'PushConfig not found'}
            if not hasattr(config, field):
                return {'success': False, 'error': f'Invalid field: {field}'}

            setattr(config, field, value)
            push_channel = config.push_channel

            rule = await s.get(ForwardRule, config.rule_id)
            if rule and rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                results = await s.execute(sync_stmt)
                for sync_obj in results.scalars().all():
                    target_config_stmt = select(PushConfig).filter_by(rule_id=sync_obj.sync_rule_id, push_channel=push_channel)
                    target_config = (await s.execute(target_config_stmt)).scalar_one_or_none()
                    if target_config and hasattr(target_config, field):
                        setattr(target_config, field, value)

            await s.commit()
            self._rule_repo.clear_cache()
            bus = self._bus
            if bus:
                await bus.publish("RULE_UPDATED", {"rule_id": int(config.rule_id), "field": field, "action": "update"})
            return {'success': True}
