from fastapi import APIRouter, Depends, Request, Query
from typing import Optional
from web_admin.security.deps import login_required
from web_admin.mappers.rule_mapper import RuleDTOMapper
from web_admin.schemas.response import ResponseSchema
from web_admin.api import deps
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["Rules Visualization"])

@router.get("/chats", response_model=ResponseSchema)
async def get_chats(
    request: Request, 
    user = Depends(login_required),
    service = Depends(deps.get_rule_query_service)
):
    """返回聊天列表用于过滤"""
    try:
        chats = await service.get_all_chats()
        return ResponseSchema(success=True, data=chats)
    except Exception as e:
        logger.error(f"获取聊天列表失败: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.get("/visualization", response_model=ResponseSchema)
async def get_visualization(
    request: Request, 
    user = Depends(login_required),
    service = Depends(deps.get_rule_query_service)
):
    """返回规则-聊天图谱数据"""
    try:
        data = await service.get_visualization_data()
        return ResponseSchema(success=True, data=data)
    except Exception as e:
        logger.error(f"获取可视化数据失败: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.get("/logs", response_model=ResponseSchema)
async def get_rule_logs(
    rule_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    user = Depends(login_required),
    stats_repo = Depends(deps.get_stats_repo)
):
    """获取规则转发日志列表"""
    try:
        items, total = await stats_repo.get_rule_logs(rule_id, page, size)
        
        data = [RuleDTOMapper.log_to_dict(item) for item in items]
        
        return ResponseSchema(
            success=True, 
            data={
                'total': total, 
                'items': data
            }
        )
    except Exception as e:
        logger.error(f"获取规则日志失败: {e}")
        return ResponseSchema(success=False, error=str(e))
