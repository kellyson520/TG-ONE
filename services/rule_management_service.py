"""
规则管理服务层 (Legacy Proxy)
This file is deprecated. Please use services.rule instead.
"""
from services.rule.facade import RuleManagementService as NewService
from services.rule.facade import rule_management_service as new_instance

# Re-export class for type hinting compatibility
class RuleManagementService(NewService):
    pass

# Re-export instance
rule_management_service = new_instance
