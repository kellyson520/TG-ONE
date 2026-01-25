from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from services.access_control_service import access_control_service
from services.audit_service import audit_service
from web_admin.security.deps import admin_required
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/security", tags=["Security"])

class ACLRuleResponse(BaseModel):
    id: int
    ip_address: str
    type: str
    reason: Optional[str]
    created_at: str
    is_active: bool

class CreateACLRuleRequest(BaseModel):
    ip_address: str
    type: str # ALLOW or BLOCK
    reason: Optional[str] = None

@router.get("/acl", response_model=List[ACLRuleResponse])
async def get_acl_rules(user = Depends(admin_required)):
    """Get all Access Control List rules."""
    rules = await access_control_service.get_all_rules()
    return [
        {
            "id": r.id,
            "ip_address": r.ip_address,
            "type": r.type,
            "reason": r.reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "is_active": r.is_active
        }
        for r in rules
    ]

@router.post("/acl")
async def add_acl_rule(
    payload: CreateACLRuleRequest,
    user = Depends(admin_required)
):
    """Add a new IP rule (Allow or Block)."""
    try:
        rule = await access_control_service.add_rule(
            ip_address=payload.ip_address,
            rule_type=payload.type,
            reason=payload.reason
        )
        
        await audit_service.log_event(
            action="ACL_ADD",
            user_id=user.id,
            username=user.username,
            resource_type="ACL",
            details={"ip": payload.ip_address, "type": payload.type},
            status="success"
        )
        
        return {"success": True, "message": "Rule added successfully"}
    except Exception as e:
        logger.error(f"Failed to add ACL rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/acl/{ip_address}")
async def delete_acl_rule(
    ip_address: str,
    user = Depends(admin_required)
):
    """Delete an ACL rule by IP."""
    try:
        success = await access_control_service.delete_rule(ip_address)
        if not success:
            raise HTTPException(status_code=404, detail="Rule not found")
            
        await audit_service.log_event(
            action="ACL_DELETE",
            user_id=user.id,
            username=user.username,
            resource_type="ACL",
            details={"ip": ip_address},
            status="success"
        )
            
        return {"success": True, "message": "Rule deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete ACL rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))
