from core.container import container

# Services
def get_rule_management_service():
    return container.rule_management_service

def get_rule_query_service():
    return container.rule_query_service

def get_config_service():
    from services.config_service import config_service
    return config_service

def get_guard_service():
    from services.system_service import guard_service
    return guard_service

def get_forward_service():
    from services.forward_service import forward_service
    return forward_service

def get_audit_service():
    from services.audit_service import audit_service
    return audit_service

def get_dedup_engine():
    from services.dedup.engine import smart_deduplicator
    return smart_deduplicator

# Repositories
def get_rule_repo():
    return container.rule_repo

def get_stats_repo():
    return container.stats_repo

def get_task_repo():
    return container.task_repo

def get_event_bus():
    return container.bus

def get_archive_manager():
    from repositories.archive_manager import get_archive_manager as _get_archive_manager
    return _get_archive_manager()

def get_settings_applier():
    from services.settings_applier import settings_applier
    return settings_applier

# Helpers
def get_ws_manager():
    from web_admin.routers.websocket_router import ws_manager
    return ws_manager

def get_exception_handler():
    from services.exception_handler import exception_handler
    return exception_handler

def get_db():
    return container.db 
    # This is container.db instance, to get session use async with container.db.get_session()
