"""
Rule Management Logic Service
Combines focused sub-modules: core, keywords, replace rules, push config, settings, import/export.
"""
from services.rule.rule_core import RuleCoreMixin
from services.rule.keyword_manager import KeywordManagerMixin
from services.rule.replace_manager import ReplaceManagerMixin
from services.rule.push_manager import PushManagerMixin
from services.rule.rule_settings import RuleSettingsMixin
from services.rule.rule_import_export import RuleImportExportMixin


class RuleLogicService(
    RuleCoreMixin,
    KeywordManagerMixin,
    ReplaceManagerMixin,
    PushManagerMixin,
    RuleSettingsMixin,
    RuleImportExportMixin,
):
    pass
