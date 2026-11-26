"""
Replace Manager - Add, copy, delete, clear, and query replace rules.
"""
from typing import Dict, Any, List
import logging

from core.helpers.error_handler import handle_errors
from schemas.sub_rules import ReplaceRuleDTO

logger = logging.getLogger(__name__)


class ReplaceManagerMixin:
    """Replace rule CRUD operations for rule management."""

    async def get_replace_rules(self, rule_id: int) -> List[ReplaceRuleDTO]:
        rule_dto = await self._rule_repo.get_by_id(rule_id)
        if not rule_dto: return []
        return rule_dto.replace_rules

    @handle_errors(default_return={'success': False, 'error': 'Adding replace rules failed'})
    async def add_replace_rules(self, rule_id: int, patterns: List[str], replacements: List[str], is_regex: bool = False) -> Dict[str, Any]:
        from models.models import ReplaceRule
        rule = await self._rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}

        existing_patterns = {rr.pattern for rr in rule.replace_rules}
        added_count = 0
        for i, pattern in enumerate(patterns):
            replacement = replacements[i] if i < len(replacements) else ""
            if pattern not in existing_patterns:
                rule.replace_rules.append(ReplaceRule(
                    pattern=pattern,
                    content=replacement
                ))
                added_count += 1

        if added_count > 0:
            await self._rule_repo.save_rule(rule)
            self._rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))

        return {'success': True, 'added': added_count}

    @handle_errors(default_return={'success': False, 'error': 'Copying replace rules failed'})
    async def copy_replace_rules_from_rule(self, source_rule_id: int, target_rule_id: int) -> Dict[str, Any]:
        from models.models import ReplaceRule
        source_rule = await self._rule_repo.get_full_rule_orm(source_rule_id)
        target_rule = await self._rule_repo.get_full_rule_orm(target_rule_id)

        if not source_rule or not target_rule:
            return {'success': False, 'error': 'Source or Target rule not found'}

        existing_replaces = {(r.pattern, r.content) for r in target_rule.replace_rules}
        added_count = 0
        skip_count = 0

        for rr in source_rule.replace_rules:
            key = (rr.pattern, rr.content)
            if key not in existing_replaces:
                target_rule.replace_rules.append(ReplaceRule(
                    pattern=rr.pattern,
                    content=rr.content
                ))
                added_count += 1
                existing_replaces.add(key)
            else:
                skip_count += 1

        if added_count > 0:
            await self._rule_repo.save_rule(target_rule)
            self._rule_repo.clear_cache(int(target_rule.source_chat.telegram_chat_id))

        return {'success': True, 'added': added_count, 'skipped': skip_count}

    @handle_errors(default_return={'success': False, 'error': 'Deleting replace rules failed'})
    async def delete_replace_rules(self, rule_id: int, patterns: List[str]) -> Dict[str, Any]:
        rule = await self._rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}

        initial_count = len(rule.replace_rules)
        rule.replace_rules = [rr for rr in rule.replace_rules if rr.pattern not in patterns]
        deleted_count = initial_count - len(rule.replace_rules)

        if deleted_count > 0:
            await self._rule_repo.save_rule(rule)
            self._rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))

        return {'success': True, 'deleted': deleted_count}

    @handle_errors(default_return={'success': False, 'error': 'Deleting replace rules by index failed'})
    async def delete_replace_rules_by_indices(self, rule_id: int, indices: List[int]) -> Dict[str, Any]:
        rule = await self._rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}

        initial_count = len(rule.replace_rules)
        valid_indices = sorted(set(i for i in indices if 1 <= i <= initial_count), reverse=True)

        if not valid_indices:
            return {'success': True, 'deleted': 0}

        for idx in valid_indices:
            del rule.replace_rules[idx - 1]

        await self._rule_repo.save_rule(rule)
        self._rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))

        return {'success': True, 'deleted': len(valid_indices)}

    @handle_errors(default_return={'success': False, 'error': 'Clearing replace rules failed'})
    async def clear_replace_rules(self, rule_id: int) -> Dict[str, Any]:
        rule = await self._rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}

        initial_count = len(rule.replace_rules)
        if initial_count == 0:
             return {'success': True, 'deleted': 0}

        rule.replace_rules.clear()

        await self._rule_repo.save_rule(rule)
        self._rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))

        return {'success': True, 'deleted': initial_count}
