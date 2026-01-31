"""
Rule Management Service Facade
Maintains backward compatibility for handlers/views while delegating to sub-services.
"""
from typing import Dict, Any, List, Optional
import logging
from services.rule.crud import RuleCRUDService
from services.rule.logic import RuleLogicService
from schemas.sub_rules import KeywordDTO, ReplaceRuleDTO

from core.aop import audit_log

logger = logging.getLogger(__name__)

class RuleManagementService:
    def __init__(self):
        self.crud = RuleCRUDService()
        self.logic = RuleLogicService()
    
    @property
    def container(self):
        from core.container import container
        return container

    # --- CRUD Delegates ---
    async def get_rule_list(self, page: int = 0, page_size: int = 10, search_query: str = None) -> Dict[str, Any]:
        return await self.crud.get_rule_list(page, page_size, search_query)

    async def get_rule_detail(self, rule_id: int) -> Dict[str, Any]:
        return await self.crud.get_rule_detail(rule_id)

    @audit_log(action="CREATE_RULE", resource_type="RULE")
    async def create_rule(self, source_chat_id: str, target_chat_id: str, **settings) -> Dict[str, Any]:
        return await self.crud.create_rule(source_chat_id, target_chat_id, **settings)

    @audit_log(action="UPDATE_RULE", resource_type="RULE")
    async def update_rule(self, rule_id: int, **settings) -> Dict[str, Any]:
        return await self.crud.update_rule(rule_id, **settings)

    @audit_log(action="DELETE_RULE", resource_type="RULE")
    async def delete_rule(self, rule_id: int) -> Dict[str, Any]:
        return await self.crud.delete_rule(rule_id)

    # --- Logic Delegates ---
    @audit_log(action="COPY_RULE", resource_type="RULE")
    async def copy_rule(self, source_rule_id: int, target_rule_id: Optional[int] = None) -> Dict[str, Any]:
        return await self.logic.copy_rule(source_rule_id, target_rule_id)

    @audit_log(action="ADD_KEYWORDS", resource_type="RULE")
    async def add_keywords(self, rule_id: int, keywords: List[str], is_regex: bool = False, is_negative: bool = False, case_sensitive: bool = False) -> Dict[str, Any]:
        # Map parameters from old signature (is_negative) to new (is_blacklist)
        return await self.logic.add_keywords(rule_id, keywords, is_regex=is_regex, is_blacklist=is_negative)

    @audit_log(action="DELETE_KEYWORDS", resource_type="RULE")
    async def delete_keywords(self, rule_id: int, keywords: List[str]) -> Dict[str, Any]:
        return await self.logic.delete_keywords(rule_id, keywords)

    @audit_log(action="CLEAR_KEYWORDS", resource_type="RULE")
    async def clear_keywords(self, rule_id: int) -> Dict[str, Any]:
        return await self.logic.clear_keywords(rule_id)

    async def get_keywords(self, rule_id: int, is_blacklist: Optional[bool] = True) -> List[KeywordDTO]:
        return await self.logic.get_keywords(rule_id, is_blacklist)

    async def get_replace_rules(self, rule_id: int) -> List[ReplaceRuleDTO]:
        return await self.logic.get_replace_rules(rule_id)

    @audit_log(action="BIND_CHAT", resource_type="CHAT")
    async def bind_chat(self, client, source_input: str, target_input: Optional[str] = None, current_chat_id: int = None) -> Dict[str, Any]:
        return await self.logic.bind_chat(client, source_input, target_input, current_chat_id)

    @audit_log(action="CLEAR_ALL_DATA", resource_type="SYSTEM")
    async def clear_all_data(self) -> Dict[str, Any]:
        return await self.logic.clear_all_data()

    async def get_rule_statistics(self) -> Dict[str, Any]:
        return await self.logic.get_rule_statistics()

    async def cleanup_orphan_chats(self, rule_deleted=None) -> int:
        return await self.logic.cleanup_orphan_chats(rule_deleted)

    # --- Pass-through / Compatibility (To be fully refactored) ---
    # Many methods from original service are specific. 
    # For now, we keep simpler delegates. 
    # If handlers call methods not listed here, they will fail unless we keep the original large file OR map everything.
    # Given the constraint of 'Finalizing', we should probably replace the original file with this Facade 
    # BUT that would break methods we haven't implemented (like import/export, replace rules etc).
    # 
    # STRATEGY:
    # We will keep `rule_management_service.py` as is, BUT modify it to inherit from Facade 
    # OR inject the new logic. 
    # Actually, the best way to 'Split' is to make `rule_management_service.py` IMPORT the sub-services
    # and delegate to them for the parts we moved, while keeping the rest until moved.

    @audit_log(action="TOGGLE_RULE_STATUS", resource_type="RULE")
    async def toggle_rule_status(self, rule_id: int, enabled: bool) -> Dict[str, Any]:
        return await self.crud.update_rule(rule_id, enable_rule=enabled)

    @audit_log(action="TOGGLE_RULE_SETTING", resource_type="RULE")
    async def toggle_rule_boolean_setting(self, rule_id: int, field: str) -> Dict[str, Any]:
        """切换规则的布尔值设置"""
        detail = await self.crud.get_rule_detail(rule_id)
        if not detail.get('success'):
            return detail
        
        current_value = detail.get(field)
        if current_value is None:
            # Try to get from settings dict if nested
            current_value = detail.get('settings', {}).get(field)
            
        if current_value is None:
             return {'success': False, 'error': f'Invalid field: {field}'}
             
        return await self.crud.update_rule(rule_id, **{field: not current_value})

    @audit_log(action="ADD_REPLACE_RULES", resource_type="RULE")
    async def add_replace_rules(self, rule_id: int, patterns: List[str], replacements: List[str], is_regex: bool = False) -> Dict[str, Any]:
        return await self.logic.add_replace_rules(rule_id, patterns, replacements, is_regex)

    @audit_log(action="DELETE_REPLACE_RULES", resource_type="RULE")
    async def delete_replace_rules(self, rule_id: int, patterns: List[str]) -> Dict[str, Any]:
        return await self.logic.delete_replace_rules(rule_id, patterns)

    @audit_log(action="CLEAR_REPLACE_RULES", resource_type="RULE")
    async def clear_replace_rules(self, rule_id: int) -> Dict[str, Any]:
        return await self.logic.clear_replace_rules(rule_id)

    @audit_log(action="EXPORT_RULE_CONFIG", resource_type="RULE")
    async def export_rule_config(self, rule_id: int, format: str = "json") -> Dict[str, Any]:
        return await self.logic.export_rule_config(rule_id, format)

    @audit_log(action="IMPORT_RULE_CONFIG", resource_type="RULE")
    async def import_rule_config(self, rule_id: int, content: str, format: str = "json") -> Dict[str, Any]:
        return await self.logic.import_rule_config(rule_id, content, format)

rule_management_service = RuleManagementService()
