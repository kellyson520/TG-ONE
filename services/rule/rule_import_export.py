"""
Rule Import/Export - Export and import rule configurations in JSON/YAML format.
"""
from typing import Dict, Any
import json
import logging

from core.helpers.error_handler import handle_errors

logger = logging.getLogger(__name__)


class RuleImportExportMixin:
    """Rule configuration import and export operations."""

    @handle_errors(default_return={'success': False, 'error': 'Export failed'})
    async def export_rule_config(self, rule_id: int, format: str = "json") -> Dict[str, Any]:
        rule_dto = await self._rule_repo.get_by_id(rule_id)
        if not rule_dto:
            return {'success': False, 'error': 'Rule not found'}

        export_data = {
            "rule": {
                "forward_mode": rule_dto.forward_mode.value if hasattr(rule_dto.forward_mode, 'value') else rule_dto.forward_mode,
                "use_bot": rule_dto.use_bot,
                "message_mode": rule_dto.message_mode.value if hasattr(rule_dto.message_mode, 'value') else rule_dto.message_mode,
                "is_replace": rule_dto.is_replace,
                "keywords": [{"k": kw.keyword, "rx": kw.is_regex, "bl": kw.is_blacklist} for kw in rule_dto.keywords],
                "replace_rules": [{"p": rr.pattern, "c": rr.content, "rx": False} for rr in rule_dto.replace_rules]
            }
        }

        if format.lower() == "yaml":
            try:
                import yaml
            except ImportError:
                return {'success': False, 'error': 'PyYAML not installed'}
            content = yaml.dump(export_data, allow_unicode=True)
        else:
            content = json.dumps(export_data, ensure_ascii=False, indent=2)

        return {'success': True, 'content': content}

    @handle_errors(default_return={'success': False, 'error': 'Import failed'})
    async def import_rule_config(self, rule_id: int, content: str, format: str = "json") -> Dict[str, Any]:
        if format.lower() == "yaml":
            try:
                import yaml
            except ImportError:
                return {'success': False, 'error': 'PyYAML not installed'}
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)

        rule_data = data.get("rule", {})

        if "keywords" in rule_data:
            for kw in rule_data["keywords"]:
                await self.add_keywords(rule_id, [kw["k"]], is_regex=kw["rx"], is_blacklist=kw["bl"])

        if "replace_rules" in rule_data:
            patterns = [rr["p"] for rr in rule_data["replace_rules"]]
            replacements = [rr["c"] for rr in rule_data["replace_rules"]]
            await self.add_replace_rules(rule_id, patterns, replacements)

        return {'success': True, 'message': 'Import successful'}
