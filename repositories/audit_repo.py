from sqlalchemy import select, func
from models.models import AuditLog
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class AuditRepository:
    def __init__(self, db):
        self.db = db

    async def create_log(
        self, 
        action: str, 
        user_id: int = None, 
        username: str = None, 
        resource_type: str = None, 
        resource_id: str = None, 
        ip_address: str = None, 
        user_agent: str = None, 
        details: dict = None, 
        status: str = "success",
        timestamp: datetime = None
    ):
        """记录审计日志"""
        try:
            async with self.db.session() as session:
                log_entry = AuditLog(
                    action=action,
                    user_id=user_id,
                    username=username,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details=json.dumps(details, ensure_ascii=False) if details else None,
                    status=status,
                    timestamp=timestamp or datetime.utcnow()
                )
                session.add(log_entry)
                await session.commit()
                return log_entry
        except Exception as e:
            logger.error(f"Failed to create audit log in repository: {e}")
            return None

    async def get_logs(
        self, 
        page: int = 1, 
        limit: int = 50, 
        user_id: int = None, 
        action: str = None, 
        start_date: datetime = None, 
        end_date: datetime = None
    ):
        """查询审计日志 (带分页)"""
        try:
            async with self.db.session() as session:
                # 1. 查询总数
                count_query = select(func.count()).select_from(AuditLog)
                if user_id:
                    count_query = count_query.filter(AuditLog.user_id == user_id)
                if action:
                    count_query = count_query.filter(AuditLog.action == action)
                if start_date:
                    count_query = count_query.filter(AuditLog.timestamp >= start_date)
                if end_date:
                    count_query = count_query.filter(AuditLog.timestamp <= end_date)
                    
                total_result = await session.execute(count_query)
                total = total_result.scalar() or 0
                
                # 2. 查询明细
                query = select(AuditLog).order_by(AuditLog.timestamp.desc())
                if user_id:
                    query = query.filter(AuditLog.user_id == user_id)
                if action:
                    query = query.filter(AuditLog.action == action)
                if start_date:
                    query = query.filter(AuditLog.timestamp >= start_date)
                if end_date:
                    query = query.filter(AuditLog.timestamp <= end_date)
                
                offset = (page - 1) * limit
                query = query.offset(offset).limit(limit)
                
                result = await session.execute(query)
                logs = result.scalars().all()
                
                return logs, total
        except Exception as e:
            logger.error(f"Failed to get audit logs in repository: {e}")
            return [], 0
