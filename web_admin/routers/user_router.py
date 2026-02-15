from fastapi import APIRouter, Depends, Request
from web_admin.schemas.response import ResponseSchema
from pydantic import BaseModel

from core.container import container
from web_admin.security.deps import admin_required
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["Users"])

# Pydantic Models
class UserSettingsUpdateRequest(BaseModel):
    # Depending on what settings are available
    pass

from web_admin.security.deps import login_required

# Routes
@router.get("/me", response_model=ResponseSchema)
async def get_current_user_profile(user = Depends(login_required)):
    """获取当前登录用户信息"""
    return ResponseSchema(success=True, data={
        'id': user.id,
        'username': user.username,
        'is_admin': user.is_admin,
        'is_2fa_enabled': getattr(user, 'is_2fa_enabled', False),
        'last_login': user.last_login.isoformat() if hasattr(user.last_login, 'isoformat') else user.last_login
    })


@router.get("", response_model=ResponseSchema)
async def list_users(user = Depends(admin_required)):
    """获取所有用户列表"""
    try:
        users = await container.user_repo.get_all_users()
        user_list = []
        for u in users:
            user_list.append({
                'id': u.id,
                'username': u.username,
                'is_admin': u.is_admin,
                'is_active': getattr(u, 'is_active', True),
                'created_at': u.created_at.isoformat() if hasattr(u.created_at, 'isoformat') else u.created_at
            })
        return ResponseSchema(success=True, data=user_list)
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        return ResponseSchema(success=False, error=str(e))


@router.post("/{user_id}/toggle_admin", response_model=ResponseSchema)
async def toggle_admin(user_id: int, user = Depends(admin_required)):
    """切换管理员权限"""
    try:
        u = await container.user_repo.get_user_by_id(user_id)
        if not u:
            return ResponseSchema(success=False, error='用户不存在')
        
        # 记录旧状态用于日志 (可选)
        new_status = not u.is_admin
        updated_user = await container.user_repo.update_user(user_id, is_admin=new_status)
        return ResponseSchema(
            success=True, 
            message=f"用户 {u.username} 管理员权限已{'开启' if new_status else '关闭'}",
            data={
                'id': updated_user.id,
                'username': updated_user.username,
                'is_admin': updated_user.is_admin,
                'is_active': getattr(updated_user, 'is_active', True)
            }
        )
    except Exception as e:
        logger.error(f"切换管理员权限失败: {e}")
        return ResponseSchema(success=False, error=str(e))


@router.post("/{user_id}/toggle_active", response_model=ResponseSchema)
async def toggle_active(user_id: int, user = Depends(admin_required)):
    """切换用户启用状态"""
    try:
        u = await container.user_repo.get_user_by_id(user_id)
        if not u:
            return ResponseSchema(success=False, error='用户不存在')
        
        new_status = not getattr(u, 'is_active', True)
        updated_user = await container.user_repo.update_user(user_id, is_active=new_status)
        return ResponseSchema(
            success=True, 
            message=f"用户 {u.username} 已{'启用' if new_status else '禁用'}",
            data={
                'id': updated_user.id,
                'username': updated_user.username,
                'is_admin': updated_user.is_admin,
                'is_active': getattr(updated_user, 'is_active', True)
            }
        )
    except Exception as e:
        logger.error(f"切换用户状态失败: {e}")
        return ResponseSchema(success=False, error=str(e))


@router.delete("/{user_id}", response_model=ResponseSchema)
async def delete_user(user_id: int, user = Depends(admin_required)):
    """删除用户"""
    try:
        if user_id == 1: # 保护初始管理员
            return ResponseSchema(success=False, error='内置管理员不能删除')
            
        success = await container.user_repo.delete_user(user_id)
        if success:
            return ResponseSchema(success=True, message='用户已删除')
        else:
            return ResponseSchema(success=False, error='删除失败')
    except Exception as e:
        logger.error(f"删除用户失败: {e}")
        return ResponseSchema(success=False, error=str(e))


@router.get("/settings", response_model=ResponseSchema)
async def get_user_settings(user = Depends(admin_required)):
    """获取用户全局设置 (例如是否允许注册)"""
    from services.system_service import system_service
    return ResponseSchema(success=True, data={'allow_registration': system_service.get_allow_registration()})


@router.post("/settings", response_model=ResponseSchema)
async def update_user_settings(request: Request, user = Depends(admin_required)):
    """更新用户全局设置"""
    try:
        from services.system_service import system_service
        payload = await request.json()
        allow = payload.get('allow_registration')
        if allow is not None:
            system_service.set_allow_registration(bool(allow))
        return ResponseSchema(success=True, message='设置已更新')
    except Exception as e:
        return ResponseSchema(success=False, error=str(e))

