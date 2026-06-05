from fastapi import APIRouter, Depends, Request, Query
from typing import Optional
from web_admin.security.deps import login_required, admin_required
from web_admin.schemas.rule_schemas import RuleCreateRequest, RuleUpdateRequest
from web_admin.mappers.rule_mapper import RuleDTOMapper
from web_admin.schemas.response import ResponseSchema
from web_admin.api import deps
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["Rules Operations"])

@router.get("", response_model=ResponseSchema)
async def get_rules(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    query: Optional[str] = Query(None),
    user = Depends(login_required),
    rule_repo = Depends(deps.get_rule_repo),
    stats_repo = Depends(deps.get_stats_repo)
):
    """返回分页后的规则列表"""
    items, total = await rule_repo.get_all(page, size, query_str=query)
    
    rules = []
    if items:
        rule_ids = [r.id for r in items]
        stats_map = await stats_repo.get_rules_stats_batch(rule_ids)
    else:
        stats_map = {}

    for r in items:
        stats = stats_map.get(r.id, {'processed': 0, 'forwarded': 0, 'error': 0})
        rules.append(RuleDTOMapper.to_dict(r, stats))
            
    return ResponseSchema(
        success=True,
        data={
            'items': rules,
            'total': total,
            'page': page,
            'size': size
        }
    )

@router.post("", response_model=ResponseSchema)
async def create_rule(
    request: Request,
    payload: RuleCreateRequest,
    user = Depends(admin_required),
    service = Depends(deps.get_rule_management_service)
):
    """创建新规则"""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[Web-API] 用户 {user.username} ({client_ip}) 正在创建规则: 来源={payload.source_chat_id}, 目标={payload.target_chat_id}, 启用={payload.enabled}, 去重={payload.enable_dedup}")
    
    try:
        result = await service.create_rule(
            payload.source_chat_id,
            payload.target_chat_id,
            enable_rule=payload.enabled,
            enable_dedup=payload.enable_dedup
        )
        
        if result['success']:
            rule_id = result.get('rule_id')
            logger.info(f"[Web-API] 用户 {user.username} 规则创建成功，ID={rule_id}")
            return ResponseSchema(
                success=True, 
                message='规则创建成功', 
                data={'rule_id': rule_id}
            )
        else:
            error_msg = result.get('error', '规则创建失败')
            logger.warning(f"[Web-API] 用户 {user.username} 规则创建失败: {error_msg}")
            return ResponseSchema(success=False, error=error_msg)
            
    except Exception as e:
        logger.error(f"[Web-API] 用户 {user.username} 创建规则失败: {e}", exc_info=True)
        return ResponseSchema(success=False, error=str(e))

@router.get("/{rule_id}", response_model=ResponseSchema)
async def get_rule_detail(
    rule_id: int,
    user = Depends(login_required),
    rule_repo = Depends(deps.get_rule_repo),
    stats_repo = Depends(deps.get_stats_repo)
):
    """获取规则详情"""
    try:
        rule = await rule_repo.get_by_id(rule_id)
        if not rule:
            return ResponseSchema(success=False, error='规则不存在')
        
        # Get real stats
        stats_map = await stats_repo.get_rules_stats_batch([rule_id])
        stats = stats_map.get(rule_id, {'processed': 0, 'forwarded': 0, 'error': 0})

        rule_dict = RuleDTOMapper.to_detail_dict(rule, stats)
        
        return ResponseSchema(success=True, data=rule_dict)
    except Exception as e:
        logger.error(f"获取规则详情失败: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.delete("/{rule_id}", response_model=ResponseSchema)
async def delete_rule(
    request: Request,
    rule_id: int,
    user = Depends(admin_required),
    service = Depends(deps.get_rule_management_service)
):
    """删除规则"""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[Web-API] 用户 {user.username} ({client_ip}) 正在删除规则，ID={rule_id}")
    
    try:
        success = await service.delete_rule(rule_id)
        if success:
            logger.info(f"[Web-API] 用户 {user.username} 规则删除成功，ID={rule_id}")
            return ResponseSchema(success=True, message=f'规则 #{rule_id} 已删除')
        else:
            logger.warning(f"[Web-API] 用户 {user.username} 规则删除失败，ID={rule_id}：规则不存在或删除失败")
            return ResponseSchema(success=False, error='规则不存在或删除失败')
    except Exception as e:
        logger.error(f"[Web-API] 用户 {user.username} 删除规则失败，ID={rule_id}：{e}", exc_info=True)
        return ResponseSchema(success=False, error=str(e))

@router.post("/{rule_id}/toggle", response_model=ResponseSchema)
async def toggle_rule(
    request: Request,
    rule_id: int,
    user = Depends(admin_required),
    service = Depends(deps.get_rule_management_service)
):
    """切换规则启用状态"""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[Web-API] 用户 {user.username} ({client_ip}) 正在切换规则状态，ID={rule_id}")
    
    try:
        result = await service.toggle_rule(rule_id)
        if result['success']:
            new_status = "启用" if result['enabled'] else "禁用"
            logger.info(f"[Web-API] 用户 {user.username} 规则状态切换成功，ID={rule_id}，新状态={new_status}")
            return ResponseSchema(
                success=True, 
                message=f"规则已{'启用' if result['enabled'] else '禁用'}",
                data={'enabled': result['enabled']}
            )
        else:
            return ResponseSchema(success=False, error=result.get('error', '切换状态失败'))
    except Exception as e:
        logger.error(f"切换规则状态失败: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.put("/{rule_id}", response_model=ResponseSchema)
async def update_rule(
    rule_id: int,
    payload: RuleUpdateRequest,
    user = Depends(admin_required),
    service = Depends(deps.get_rule_management_service)
):
    """更新规则"""
    try:
        update_data = {}
        
        # Map all fields from payload to update_data
        field_mapping = {
            'enabled': 'enable_rule',
            'enable_dedup': 'enable_dedup',
            'target_chat_id': 'target_chat_id',
            'use_bot': 'use_bot',
            'force_pure_forward': 'force_pure_forward',
            'is_original_link': 'is_original_link',
            'is_original_sender': 'is_original_sender',
            'is_original_time': 'is_original_time',
            'is_delete_original': 'is_delete_original',
            'enable_delay': 'enable_delay',
            'delay_seconds': 'delay_seconds',
            'enable_media_size_filter': 'enable_media_size_filter',
            'max_media_size': 'max_media_size',
            'enable_media_type_filter': 'enable_media_type_filter',
            'is_ai': 'is_ai',
            'ai_model': 'ai_model',
            'ai_prompt': 'ai_prompt',
            'description': 'description'
        }
        
        for payload_field, db_field in field_mapping.items():
            value = getattr(payload, payload_field, None)
            if value is not None:
                update_data[db_field] = value
            
        if not update_data:
             return ResponseSchema(success=True, message='没有更新项')
             
        result = await service.update_rule(rule_id, **update_data)
        
        if result.get('success'):
            return ResponseSchema(success=True, message='规则更新成功')
        else:
            return ResponseSchema(success=False, error=result.get('error', '更新失败'))
    except Exception as e:
        logger.error(f"更新规则失败: {e}")
        return ResponseSchema(success=False, error=str(e))
