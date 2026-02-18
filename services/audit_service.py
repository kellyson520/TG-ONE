import logging
from datetime import datetime
from core.container import container

logger = logging.getLogger(__name__)

class AuditService:
    """
    审计日志服务
    负责记录和查询系统的所有的安全相关操作日志
    """
    
    def __init__(self):
        from core.archive.bridge import UnifiedQueryBridge
        self.bridge = UnifiedQueryBridge()
    
    async def log_event(
        self,
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

    async def get_logs(
        self,
        page: int = 1, 
        limit: int = 50,
        user_id: int = None,
        action: str = None,
        start_date: datetime = None,
        end_date: datetime = None
    ):
        """
        查询审计日志 (支持热冷联邦查询)
        """
        offset = (page - 1) * limit
        logs = await self.bridge.list_audit_logs(
            user_id=user_id,
            action=action,
            limit=limit,
            offset=offset
        )
        
        # 兼容旧接口的 total 统计 (可选，这里先返回 logs 和近似 total)
        # 如果需要精准 total，需要跨层 count
        total = 0
        if logs:
            res = await self.bridge.query_aggregate("audit_logs", "SELECT COUNT(*) as cnt FROM {table}")
            total = res[0]['cnt'] if res else len(logs)
            
        return logs, total

audit_service = AuditService()
