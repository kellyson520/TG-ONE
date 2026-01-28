"""
Modular Models Proxy
This file maintains backward compatibility while redirecting to split model files.
"""
from models.base import Base
from models.chat import Chat
from models.rule import (
    ForwardRule, ForwardMapping, Keyword, ReplaceRule, 
    MediaTypes, MediaExtensions, RuleSync, PushConfig, 
    RSSConfig, RSSPattern
)
from models.user import User, AuditLog, ActiveSession, AccessControlList
from models.stats import ChatStatistics, RuleStatistics, RuleLog
from models.system import SystemConfiguration, ErrorLog, TaskQueue, RSSSubscription
from models.dedup import MediaSignature
from models.migration import migrate_db

# Re-export all for backward compatibility
__all__ = [
    'Base',
    'Chat',
    'ForwardRule', 'ForwardMapping', 'Keyword', 'ReplaceRule', 
    'MediaTypes', 'MediaExtensions', 'RuleSync', 'PushConfig', 
    'RSSConfig', 'RSSPattern',
    'User', 'AuditLog', 'ActiveSession', 'AccessControlList',
    'ChatStatistics', 'RuleStatistics', 'RuleLog',
    'SystemConfiguration', 'ErrorLog', 'TaskQueue', 'RSSSubscription',
    'MediaSignature', 'migrate_db'
]
