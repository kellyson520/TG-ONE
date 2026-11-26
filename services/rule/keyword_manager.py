"""
Keyword Manager - Add, copy, delete, clear, and query keywords.
"""
from typing import Dict, Any, List, Optional
import logging

from core.helpers.error_handler import handle_errors
from schemas.sub_rules import KeywordDTO

logger = logging.getLogger(__name__)


class KeywordManagerMixin:
    """Keyword CRUD operations for rule management."""

    @handle_errors(default_return={'success': False, 'error': 'Adding keywords failed'})
    async def add_keywords(self, rule_id: int, keywords: List[str], is_regex: bool = False, is_blacklist: bool = False) -> Dict[str, Any]:
        from models.models import Keyword
        rule = await self._rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}

        existing_kws = {kw.keyword for kw in rule.keywords if kw.is_blacklist == is_blacklist}
        added_count = 0
        for kw_text in keywords:
            if kw_text not in existing_kws:
                rule.keywords.append(Keyword(
                    keyword=kw_text,
                    is_regex=is_regex,
                    is_blacklist=is_blacklist
                ))
                added_count += 1

        if added_count > 0:
            await self._rule_repo.save_rule(rule)
            self._rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))

        return {'success': True, 'added': added_count}

    @handle_errors(default_return={'success': False, 'error': 'Copying keywords failed'})
    async def copy_keywords_from_rule(self, source_rule_id: int, target_rule_id: int, is_regex: Optional[bool] = None) -> Dict[str, Any]:
        from models.models import Keyword
        source_rule = await self._rule_repo.get_full_rule_orm(source_rule_id)
        target_rule = await self._rule_repo.get_full_rule_orm(target_rule_id)

        if not source_rule or not target_rule:
            return {'success': False, 'error': 'Source or Target rule not found'}

        existing_kws = {(kw.keyword, kw.is_regex, kw.is_blacklist) for kw in target_rule.keywords}
        added_count = 0
        skip_count = 0

        for kw in source_rule.keywords:
            if is_regex is not None and kw.is_regex != is_regex:
                continue

            key = (kw.keyword, kw.is_regex, kw.is_blacklist)
            if key not in existing_kws:
                target_rule.keywords.append(Keyword(
                    keyword=kw.keyword,
                    is_regex=kw.is_regex,
                    is_blacklist=kw.is_blacklist
                ))
                added_count += 1
                existing_kws.add(key)
            else:
                skip_count += 1

        if added_count > 0:
            await self._rule_repo.save_rule(target_rule)
            self._rule_repo.clear_cache(int(target_rule.source_chat.telegram_chat_id))

        return {'success': True, 'added': added_count, 'skipped': skip_count}

    @handle_errors(default_return={'success': False, 'error': 'Deleting keywords failed'})
    async def delete_keywords(self, rule_id: int, keywords: List[str]) -> Dict[str, Any]:
        rule = await self._rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}

        initial_count = len(rule.keywords)
        rule.keywords = [kw for kw in rule.keywords if kw.keyword not in keywords]
        deleted_count = initial_count - len(rule.keywords)

        if deleted_count > 0:
            await self._rule_repo.save_rule(rule)
            self._rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))

        return {'success': True, 'deleted': deleted_count}

    @handle_errors(default_return={'success': False, 'error': 'Deleting keywords by index failed'})
    async def delete_keywords_by_indices(self, rule_id: int, indices: List[int]) -> Dict[str, Any]:
        rule = await self._rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}

        initial_count = len(rule.keywords)
        valid_indices = sorted(set(i for i in indices if 1 <= i <= initial_count), reverse=True)

        if not valid_indices:
            return {'success': True, 'deleted': 0}

        for idx in valid_indices:
            del rule.keywords[idx - 1]

        await self._rule_repo.save_rule(rule)
        self._rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))

        return {'success': True, 'deleted': len(valid_indices)}

    @handle_errors(default_return={'success': False, 'error': 'Clearing keywords failed'})
    async def clear_keywords(self, rule_id: int) -> Dict[str, Any]:
        rule = await self._rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}

        initial_count = len(rule.keywords)
        if initial_count == 0:
             return {'success': True, 'deleted': 0}

        rule.keywords.clear()

        await self._rule_repo.save_rule(rule)
        self._rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))

        return {'success': True, 'deleted': initial_count}

    async def get_keywords(self, rule_id: int, is_blacklist: Optional[bool] = True) -> List[KeywordDTO]:
        rule_dto = await self._rule_repo.get_by_id(rule_id)
        if not rule_dto: return []
        if is_blacklist is None:
            return rule_dto.keywords
        return [kw for kw in rule_dto.keywords if kw.is_blacklist == is_blacklist]
