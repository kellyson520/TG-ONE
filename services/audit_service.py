import logging
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from models.models import AuditLog
from core.container import container
import json

logger = logging.getLogger(__name__)

class AuditService:
    """
    审计日志服务
    负责记录和查询系统的所有的安全相关操作日志
    """
    
    @staticmethod
    async def log_event(
        action: str,
        user_id: int = None,
        username: str = None,
        resource_type: str = None,
        resource_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        details: dict = None,
        status: str = "success"
    ):
        """
        记录审计日志 (通过 Repository)
        """
        return await container.audit_repo.create_log(
            action=action,
            user_id=user_id,
            username=username,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            status=status
        )

    @staticmethod
    async def get_logs(
        page: int = 1, 
        limit: int = 50,
        user_id: int = None,
        action: str = None,
        start_date: datetime = None,
        end_date: datetime = None
    ):
        """
        查询审计日志 (通过 Repository)
        """
        return await container.audit_repo.get_logs(
            page=page,
            limit=limit,
            user_id=user_id,
            action=action,
            start_date=start_date,
            end_date=end_date
        )

audit_service = AuditService()
