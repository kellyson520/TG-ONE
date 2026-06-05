import functools
import logging
import asyncio
from typing import Any
from core.context import user_id_var, username_var, ip_address_var, user_agent_var
# from services.audit_service import audit_service (Moved to lazy inside finally)

logger = logging.getLogger(__name__)

def audit_log(action: str, resource_type: str = None):
    """
    Audit Log Decorator (AOP)
    
    Automatically records audit logs for sensitive Service methods.
    Context is captured from `core.context` (populated by Middleware).
    
    Usage:
        @audit_log(action="DELETE_RULE", resource_type="RULE")
        async def delete_rule(self, rule_id: int): ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # 1. Capture Context
            user_id = user_id_var.get()
            username = username_var.get()
            ip = ip_address_var.get()
            ua = user_agent_var.get()
            
            status = "success"
            details = {
                "method": func.__name__, 
                "args": str(kwargs)  # Careful with sensitive data here, maybe filter?
            }
            
            try:
                # 2. Execute Business Logic
                result = await func(*args, **kwargs)
                return result
            
            except Exception as e:
                status = "failure"
                details["error"] = str(e)
                raise e
                
            finally:
                # 3. Async Log (Non-blocking)
                # Attempt to find common ID patterns in kwargs
                # Priority: rule_id > user_id > id
                valid_id = (
                    kwargs.get("rule_id") or 
                    kwargs.get("user_id") or 
                    kwargs.get("id")
                )
                resource_id = str(valid_id) if valid_id is not None else None
                
                # If valid user action (even if anonymous/system), log it
                try:
                    from services.audit_service import audit_service
                    asyncio.create_task(
                        audit_service.log_event(
                            action=action,
                            user_id=user_id,
                            username=username,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            ip_address=ip,
                            user_agent=ua,
                            status=status,
                            details=details
                        )
                    )
                except ImportError:
                    logger.warning("Audit service not available for AOP logging")
        return wrapper
    return decorator
