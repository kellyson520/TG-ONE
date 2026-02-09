from typing import List, Dict, Optional, Any
from sqlalchemy import select, delete, desc
from sqlalchemy.orm import selectinload
from models.models import ActiveSession
from werkzeug.user_agent import UserAgent
import logging

logger = logging.getLogger(__name__)

class ActiveSessionService:
    """
    Service for managing Active Web Sessions.
    Handles listing, parsing device info, and revocation.
    Phase 2 Security Task 2.2
    """
    
    def _parse_ua(self, ua_string: str) -> str:
        """Parse User-Agent string to human readable device info"""
        if not ua_string:
            return "Unknown Device"
        try:
            ua = UserAgent(ua_string)
            browser = ua.browser
            platform = ua.platform
            if browser and platform:
                return f"{platform} / {browser}"
            return ua_string[:50]
        except Exception:
            return ua_string[:50]

    async def get_all_sessions(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all active sessions, optionally filtered by user_id.
        Enriches data with parsed device info.
        """
        from core.container import container
        async with container.db.get_session() as session:
            stmt = select(ActiveSession).options(selectinload(ActiveSession.user))
            if user_id:
                stmt = stmt.where(ActiveSession.user_id == user_id)
            stmt = stmt.order_by(desc(ActiveSession.created_at))
            
            result = await session.execute(stmt)
            sessions = result.scalars().all()
            
            data = []
            for s in sessions:
                # Parse device info from user agent
                info = self._parse_ua(s.user_agent)
                    
                data.append({
                    "id": s.id,
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "username": s.user.username if s.user else "Unknown",
                    "ip_address": s.ip_address,
                    "device_info": info,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
                    "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                    "is_active": True # If it exists in DB, it is active (unless expired)
                })
            return data

    async def revoke_session(self, session_id: int) -> bool:
        """Revoke a specific session by Primary Key ID"""
        from core.container import container
        async with container.db.get_session() as session:
            stmt = select(ActiveSession).where(ActiveSession.id == session_id)
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
            if obj:
                await session.delete(obj)
                await session.commit()
                logger.info(f"Revoked session {session_id}")
                return True
            return False

    async def revoke_user_sessions(self, user_id: int, exclude_session_id: Optional[str] = None):
        """Revoke all sessions for a user, optionally keeping current one"""
        from core.container import container
        async with container.db.get_session() as session:
             stmt = delete(ActiveSession).where(ActiveSession.user_id == user_id)
             if exclude_session_id:
                 stmt = stmt.where(ActiveSession.session_id != exclude_session_id)
             await session.execute(stmt)
             await session.commit()
             logger.info(f"Revoked sessions for user {user_id}")

active_session_service = ActiveSessionService()
