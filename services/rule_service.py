"""
转发规则查询服务模块 (Legacy Proxy)
This file is deprecated. Please use services.rule.query instead.
"""
from services.rule.query import RuleQueryService as NewService

# Re-export class for type hinting compatibility
class RuleQueryService(NewService):
    """转发规则查询服务 (Legacy Proxy)"""
    pass

# For those who might import specific module contents or attempt to patch them
