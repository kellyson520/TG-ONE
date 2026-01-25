from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from models.models import AccessControlList
from core.container import container
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AccessControlService:
    def __init__(self):
        self._rules_cache = None
        self._last_refresh = None

    async def _get_rules(self) -> List[AccessControlList]:
        """Get rules with simple 60s cache."""
        if self._rules_cache is not None and self._last_refresh:
            if (datetime.utcnow() - self._last_refresh).total_seconds() < 60:
                return self._rules_cache
        
        async with container.db.session() as session:
            stmt = select(AccessControlList).where(AccessControlList.is_active == True)
            result = await session.execute(stmt)
            self._rules_cache = result.scalars().all()
            self._last_refresh = datetime.utcnow()
            return self._rules_cache

    def _invalidate_cache(self):
        self._rules_cache = None
        self._last_refresh = None

    async def check_ip_access(self, ip_address_str: str) -> bool:
        """
        Check if an IP is allowed to access the system.
        Supports CIDR notation (e.g. 192.168.1.0/24).
        Logic:
        1. If IP in Blacklist -> Deny (False)
        2. If Whitelist exists (any ALLOW rule) AND IP not in Whitelist -> Deny (False)
        3. Default -> Allow (True)
        """
        import ipaddress
        try:
            client_ip = ipaddress.ip_address(ip_address_str)
        except ValueError:
            logger.error(f"Invalid client IP format: {ip_address_str}")
            return False

        rules = await self._get_rules()
        
        # Separate rules
        blacklist = [r for r in rules if r.type == 'BLOCK']
        whitelist = [r for r in rules if r.type == 'ALLOW']

        # 1. Check Blacklist (Fast string match first, then network match)
        for rule in blacklist:
            try:
                if not rule.ip_address:
                    continue
                    
                # If rule has '/', it's CIDR
                if '/' in rule.ip_address:
                    if client_ip in ipaddress.ip_network(rule.ip_address, strict=False):
                        logger.warning(f"Access denied for blocked network: {rule.ip_address} (Client: {ip_address_str})")
                        return False
                else:
                    if ip_address_str == rule.ip_address:
                        logger.warning(f"Access denied for blocked IP: {ip_address_str}")
                        return False
            except Exception:
                continue

        # 2. Check Whitelist
        if whitelist:
            allowed = False
            for rule in whitelist:
                try:
                    if '/' in rule.ip_address:
                        if client_ip in ipaddress.ip_network(rule.ip_address, strict=False):
                            allowed = True
                            break
                    else:
                        if ip_address_str == rule.ip_address:
                            allowed = True
                            break
                except Exception:
                    continue
            
            if not allowed:
                logger.warning(f"Access denied for IP not in whitelist: {ip_address_str}")
                return False
        
        return True

    async def add_rule(self, ip_address: str, rule_type: str, reason: Optional[str] = None) -> AccessControlList:
        """Add an IP rule (ALLOW or BLOCK)."""
        rule_type = rule_type.upper()
        if rule_type not in ['ALLOW', 'BLOCK']:
            raise ValueError("Invalid rule type. Must be ALLOW or BLOCK.")
            
        async with container.db.session() as session:
            # Check existing
            stmt = select(AccessControlList).where(AccessControlList.ip_address == ip_address)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.type = rule_type
                existing.reason = reason
                existing.is_active = True
                existing.created_at = datetime.utcnow()
                await session.commit()
                self._invalidate_cache()
                return existing
            
            new_rule = AccessControlList(
                ip_address=ip_address,
                type=rule_type,
                reason=reason
            )
            session.add(new_rule)
            await session.commit()
            self._invalidate_cache()
            return new_rule

    async def delete_rule(self, ip_address: str) -> bool:
        """Delete a rule by IP."""
        async with container.db.session() as session:
            stmt = select(AccessControlList).where(AccessControlList.ip_address == ip_address)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            
            if rule:
                await session.delete(rule)
                await session.commit()
                self._invalidate_cache()
                return True
            return False

    async def get_all_rules(self) -> List[AccessControlList]:
        """Get all ACL rules."""
        async with container.db.session() as session:
            stmt = select(AccessControlList).order_by(AccessControlList.created_at.desc())
            result = await session.execute(stmt)
            return result.scalars().all()

access_control_service = AccessControlService()
