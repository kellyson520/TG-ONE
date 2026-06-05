from fastapi import APIRouter, Depends, Request
from web_admin.security.deps import admin_required
from web_admin.schemas.rule_schemas import KeywordAddRequest, ReplaceRuleAddRequest
from web_admin.schemas.response import ResponseSchema
from web_admin.api import deps
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["Rules Content"])

@router.post("/{rule_id}/keywords", response_model=ResponseSchema)
async def add_keywords(
    rule_id: int,
    payload: KeywordAddRequest,
    user = Depends(admin_required),
    service = Depends(deps.get_rule_management_service)
):
    """添加关键字到规则"""
    try:
        result = await service.add_keywords(
            rule_id,
            payload.keywords,
            is_regex=payload.is_regex,
            is_negative=payload.is_negative,
            case_sensitive=payload.case_sensitive
        )
        if result['success']:
            return ResponseSchema(success=True, message=f"成功添加 {result['count']} 个关键字")
        else:
            return ResponseSchema(success=False, error=result.get('error', '添加关键字失败'))
    except Exception as e:
        logger.error(f"添加关键字失败: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.delete("/{rule_id}/keywords", response_model=ResponseSchema)
async def delete_keywords(
    rule_id: int,
    payload: KeywordAddRequest, 
    user = Depends(admin_required),
    service = Depends(deps.get_rule_management_service)
):
    """从规则中删除关键字"""
    try:
        result = await service.delete_keywords(
            rule_id,
            payload.keywords
        )
        if result['success']:
            return ResponseSchema(success=True, message=f"成功删除 {result['count']} 个关键字")
        else:
            return ResponseSchema(success=False, error=result.get('error', '删除关键字失败'))
    except Exception as e:
        logger.error(f"删除关键字失败: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.post("/{rule_id}/replace-rules", response_model=ResponseSchema)
async def add_replace_rules(
    rule_id: int,
    payload: ReplaceRuleAddRequest,
    user = Depends(admin_required),
    service = Depends(deps.get_rule_management_service)
):
    """添加替换规则到基础规则"""
    try:
        result = await service.add_replace_rules(
            rule_id,
            patterns=[payload.pattern],
            replacements=[payload.replacement],
            is_regex=payload.is_regex
        )
        if result['success']:
            return ResponseSchema(success=True, message='替换规则添加成功')
        else:
            return ResponseSchema(success=False, error=result.get('error', '添加替换规则失败'))
    except Exception as e:
        logger.error(f"添加替换规则失败: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.delete("/{rule_id}/replace-rules", response_model=ResponseSchema)
async def delete_replace_rules(
    request: Request,
    rule_id: int,
    user = Depends(admin_required),
    service = Depends(deps.get_rule_management_service)
):
    """从规则中删除替换规则"""
    try:
        payload = await request.json()
        pattern = payload.get('pattern')
        if not pattern:
            return ResponseSchema(success=False, error='未指定要删除的模式')
            
        result = await service.delete_replace_rule(rule_id, pattern)
        if result['success']:
            return ResponseSchema(success=True, message='替换规则已删除')
        else:
            return ResponseSchema(success=False, error=result.get('error', '删除失败'))
    except Exception as e:
        logger.error(f"删除替换规则失败: {e}")
        return ResponseSchema(success=False, error=str(e))
