from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from core.container import container
from web_admin.security.deps import login_required, admin_required
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["Rules"])

# Pydantic Models
class KeywordAddRequest(BaseModel):
    keywords: List[str]
    is_regex: bool = False
    is_negative: bool = False
    case_sensitive: bool = False

class ReplaceRuleAddRequest(BaseModel):
    pattern: str
    replacement: str
    is_regex: bool = False

class RuleCreateRequest(BaseModel):
    source_chat_id: str
    target_chat_id: str
    enabled: bool = True
    enable_dedup: bool = False

class RuleUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    enable_dedup: Optional[bool] = None
    target_chat_id: Optional[str] = None
    use_bot: Optional[bool] = None
    force_pure_forward: Optional[bool] = None
    is_original_link: Optional[bool] = None
    is_original_sender: Optional[bool] = None
    is_original_time: Optional[bool] = None
    is_delete_original: Optional[bool] = None
    enable_delay: Optional[bool] = None
    delay_seconds: Optional[int] = None
    enable_media_size_filter: Optional[bool] = None
    max_media_size: Optional[int] = None
    enable_media_type_filter: Optional[bool] = None
    is_ai: Optional[bool] = None
    ai_model: Optional[str] = None
    ai_prompt: Optional[str] = None
    description: Optional[str] = None

# Routes
@router.get("", response_class=JSONResponse)
async def get_rules(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    user = Depends(login_required)
):
    """返回分页后的规则列表"""
    items, total = await container.rule_repo.get_all(page, size)
    
    rules = []
    if items:
        rule_ids = [r.id for r in items]
        stats_map = await container.stats_repo.get_rules_stats_batch(rule_ids)
    else:
        stats_map = {}

    for r in items:
        # Get stats for this rule
        stats = stats_map.get(r.id, {'processed': 0, 'forwarded': 0, 'error': 0})
        
        # Serialize rule
        rule_dict = {
            "id": r.id,
            "source_chat_id": r.source_chat_id,
            "target_chat_id": r.target_chat_id,
            "enabled": r.enable_rule,
            "enable_dedup": r.enable_dedup,
            "forward_mode": r.forward_mode.value if hasattr(r.forward_mode, 'value') else r.forward_mode,
            "keywords_count": len(r.keywords) if r.keywords else 0,
            "replace_rules_count": len(r.replace_rules) if r.replace_rules else 0,
            "forwards": stats['forwarded'],  # Added: Total forwarded count
            "processed": stats['processed'], # Added: Total processed count
            "errors": stats['error'],        # Added: Total error count
            "source_chat": {
                "id": r.source_chat.id,
                "title": r.source_chat.name,
                "telegram_chat_id": r.source_chat.telegram_chat_id,
                "username": r.source_chat.username
            } if r.source_chat else None,
            "target_chat": {
                "id": r.target_chat.id,
                "title": r.target_chat.name,
                "telegram_chat_id": r.target_chat.telegram_chat_id,
                "username": r.target_chat.username
            } if r.target_chat else None
        }
        rules.append(rule_dict)
            
    return JSONResponse({
        'success': True, 
        'data': {
            'items': rules,
            'total': total,
            'page': page,
            'size': size
        }
    })

@router.post("", response_class=JSONResponse)
async def create_rule(
    request: Request,
    payload: RuleCreateRequest,
    user = Depends(admin_required)
):
    """创建新规则"""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[Web-API] 用户 {user.username} ({client_ip}) 正在创建规则: 来源={payload.source_chat_id}, 目标={payload.target_chat_id}, 启用={payload.enabled}, 去重={payload.enable_dedup}")
    
    try:
        result = await container.rule_management_service.create_rule(
            payload.source_chat_id,
            payload.target_chat_id,
            enable_rule=payload.enabled,
            enable_dedup=payload.enable_dedup
        )
        
        if result['success']:
            rule_id = result.get('rule_id')
            logger.info(f"[Web-API] 用户 {user.username} 规则创建成功，ID={rule_id}")
            return JSONResponse({
                'success': True, 
                'message': '规则创建成功', 
                'rule_id': rule_id
            })
        else:
            error_msg = result.get('error', '规则创建失败')
            logger.warning(f"[Web-API] 用户 {user.username} 规则创建失败: {error_msg}")
            return JSONResponse({'success': False, 'error': error_msg})
            
    except Exception as e:
        logger.error(f"[Web-API] 用户 {user.username} 创建规则失败: {e}", exc_info=True)
        return JSONResponse({'success': False, 'error': str(e)})

@router.get("/chats", response_class=JSONResponse)
async def get_chats(request: Request, user = Depends(login_required)):
    """返回聊天列表用于过滤"""
    try:
        chats = await container.rule_query_service.get_all_chats()
        return JSONResponse({'success': True, 'data': chats})
    except Exception as e:
        logger.error(f"获取聊天列表失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)})

@router.get("/visualization", response_class=JSONResponse)
async def get_visualization(request: Request, user = Depends(login_required)):
    """返回规则-聊天图谱数据"""
    try:
        data = await container.rule_query_service.get_visualization_data()
        return JSONResponse({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"获取可视化数据失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)})

@router.get("/logs", response_class=JSONResponse)
async def get_rule_logs(
    rule_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    user = Depends(login_required)
):
    """获取规则转发日志列表"""
    try:
        items, total = await container.stats_repo.get_rule_logs(rule_id, page, size)
        
        data = []
        for item in items:
            # Try to get chat info from rule relation if available
            source_title = "Unknown"
            target_title = "Unknown"
            try:
                if item.rule:
                    if item.rule.source_chat:
                        source_title = item.rule.source_chat.title or item.rule.source_chat.username or str(item.rule.source_chat.telegram_chat_id)
                    if item.rule.target_chat:
                        target_title = item.rule.target_chat.title or item.rule.target_chat.username or str(item.rule.target_chat.telegram_chat_id)
            except Exception:
                pass # Relationship might not be loaded

            data.append({
                'id': item.id,
                'rule_id': item.rule_id,
                'source_message_id': item.source_message_id,
                'action': item.action,
                'result': item.result,
                'created_at': item.created_at,
                'source_chat': source_title,
                'target_chat': target_title
            })
        
        return JSONResponse({
            'success': True, 
            'data': {
                'total': total, 
                'items': data
            }
        })
    except Exception as e:
        logger.error(f"获取规则日志失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.get("/{rule_id}", response_class=JSONResponse)
async def get_rule_detail(
    rule_id: int,
    user = Depends(login_required)
):
    """获取规则详情"""
    try:
        rule = await container.rule_repo.get_by_id(rule_id)
        if not rule:
            return JSONResponse({'success': False, 'error': '规则不存在'}, status_code=404)
        
        # Get real stats
        stats_map = await container.stats_repo.get_rules_stats_batch([rule_id])
        stats = stats_map.get(rule_id, {'processed': 0, 'forwarded': 0, 'error': 0})

        # Build complete rule details
        rule_dict = {

            "id": rule.id,
            "source_chat_id": rule.source_chat_id,
            "target_chat_id": rule.target_chat_id,
            "enabled": rule.enable_rule,
            "enable_dedup": rule.enable_dedup,
            "forward_mode": rule.forward_mode.value if hasattr(rule.forward_mode, 'value') else str(rule.forward_mode),
            "use_bot": rule.use_bot,
            "message_mode": rule.message_mode.value if hasattr(rule.message_mode, 'value') else str(rule.message_mode),
            "is_replace": rule.is_replace,
            "is_preview": rule.is_preview.value if hasattr(rule.is_preview, 'value') else str(rule.is_preview),
            "is_original_link": rule.is_original_link,
            "is_delete_original": rule.is_delete_original,
            "is_original_sender": rule.is_original_sender,
            "is_original_time": rule.is_original_time,
            "force_pure_forward": rule.force_pure_forward,
            "enable_delay": rule.enable_delay,
            "delay_seconds": rule.delay_seconds,
            "max_media_size": rule.max_media_size,
            "enable_media_size_filter": rule.enable_media_size_filter,
            "enable_media_type_filter": rule.enable_media_type_filter,
            "is_ai": rule.is_ai,
            "ai_model": rule.ai_model,
            "ai_prompt": rule.ai_prompt,
            "description": rule.description,
            "priority": rule.priority,
            "created_at": rule.created_at,
            "updated_at": rule.updated_at,
            "updated_at": rule.updated_at,
            "message_count": stats.get('forwarded', 0),
            "processed_count": stats.get('processed', 0),
            "error_count": stats.get('error', 0),
            "source_chat": {
                "id": rule.source_chat.id,
                "title": rule.source_chat.name,
                "telegram_chat_id": rule.source_chat.telegram_chat_id,
                "username": rule.source_chat.username
            } if rule.source_chat else None,
            "target_chat": {
                "id": rule.target_chat.id,
                "title": rule.target_chat.name,
                "telegram_chat_id": rule.target_chat.telegram_chat_id,
                "username": rule.target_chat.username
            } if rule.target_chat else None,
            "keywords": [
                {"id": kw.id, "keyword": kw.keyword, "is_regex": kw.is_regex, "is_blacklist": getattr(kw, 'is_blacklist', False)}
                for kw in (rule.keywords or [])
            ],
            "replace_rules": [
                {"id": rr.id, "pattern": rr.pattern, "content": rr.content}
                for rr in (rule.replace_rules or [])
            ]
        }
        
        return JSONResponse({'success': True, 'data': rule_dict})
    except Exception as e:
        logger.error(f"获取规则详情失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)


@router.delete("/{rule_id}", response_class=JSONResponse)
async def delete_rule(
    request: Request,
    rule_id: int,
    user = Depends(admin_required)
):
    """删除规则"""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[Web-API] 用户 {user.username} ({client_ip}) 正在删除规则，ID={rule_id}")
    
    try:
        success = await container.rule_management_service.delete_rule(rule_id)
        if success:
            logger.info(f"[Web-API] 用户 {user.username} 规则删除成功，ID={rule_id}")
            return JSONResponse({'success': True, 'message': f'规则 #{rule_id} 已删除'})
        else:
            logger.warning(f"[Web-API] 用户 {user.username} 规则删除失败，ID={rule_id}：规则不存在或删除失败")
            return JSONResponse({'success': False, 'error': '规则不存在或删除失败'})
    except Exception as e:
        logger.error(f"[Web-API] 用户 {user.username} 删除规则失败，ID={rule_id}：{e}", exc_info=True)
        return JSONResponse({'success': False, 'error': str(e)})

@router.post("/{rule_id}/toggle", response_class=JSONResponse)
async def toggle_rule(
    request: Request,
    rule_id: int,
    user = Depends(admin_required)
):
    """切换规则启用状态"""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[Web-API] 用户 {user.username} ({client_ip}) 正在切换规则状态，ID={rule_id}")
    
    try:
        result = await container.rule_management_service.toggle_rule(rule_id)
        if result['success']:
            new_status = "启用" if result['enabled'] else "禁用"
            logger.info(f"[Web-API] 用户 {user.username} 规则状态切换成功，ID={rule_id}，新状态={new_status}")
            return JSONResponse({
                'success': True, 
                'message': f"规则已{'启用' if result['enabled'] else '禁用'}",
                'data': {'enabled': result['enabled']}
            })
        else:
            return JSONResponse({'success': False, 'error': result.get('error', '切换状态失败')})
    except Exception as e:
        logger.error(f"切换规则状态失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)})

@router.post("/{rule_id}/keywords", response_class=JSONResponse)
async def add_keywords(
    rule_id: int,
    payload: KeywordAddRequest,
    user = Depends(admin_required)
):
    """添加关键字到规则"""
    try:
        result = await container.rule_management_service.add_keywords(
            rule_id,
            payload.keywords,
            is_regex=payload.is_regex,
            is_negative=payload.is_negative,
            case_sensitive=payload.case_sensitive
        )
        if result['success']:
            return JSONResponse({'success': True, 'message': f"成功添加 {result['count']} 个关键字"})
        else:
            return JSONResponse({'success': False, 'error': result.get('error', '添加关键字失败')})
    except Exception as e:
        logger.error(f"添加关键字失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)})

@router.post("/{rule_id}/replace-rules", response_class=JSONResponse)
async def add_replace_rules(
    rule_id: int,
    payload: ReplaceRuleAddRequest,
    user = Depends(admin_required)
):
    """添加替换规则到基础规则"""
    try:
        result = await container.rule_management_service.add_replace_rules(
            rule_id,
            patterns=[payload.pattern],
            replacements=[payload.replacement],
            is_regex=payload.is_regex
        )
        if result['success']:
            return JSONResponse({'success': True, 'message': '替换规则添加成功'})
        else:
            return JSONResponse({'success': False, 'error': result.get('error', '添加替换规则失败')})
    except Exception as e:
        logger.error(f"添加替换规则失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)})
@router.put("/{rule_id}", response_class=JSONResponse)
async def update_rule(
    rule_id: int,
    payload: RuleUpdateRequest,
    user = Depends(admin_required)
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
             return JSONResponse({'success': True, 'message': '没有更新项'})
             
        # RuleManagementService has update_rule (usually via Repo or direct fields)
        result = await container.rule_management_service.update_rule(rule_id, **update_data)
        
        if result.get('success'):
            return JSONResponse({'success': True, 'message': '规则更新成功'})
        else:
            return JSONResponse({'success': False, 'error': result.get('error', '更新失败')})
    except Exception as e:
        logger.error(f"更新规则失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)})

@router.delete("/{rule_id}/keywords", response_class=JSONResponse)
async def delete_keywords(
    rule_id: int,
    payload: KeywordAddRequest, 
    user = Depends(admin_required)
):
    """从规则中删除关键字"""
    try:
        result = await container.rule_management_service.delete_keywords(
            rule_id,
            payload.keywords
        )
        if result['success']:
            return JSONResponse({'success': True, 'message': f"成功删除 {result['count']} 个关键字"})
        else:
            return JSONResponse({'success': False, 'error': result.get('error', '删除关键字失败')})
    except Exception as e:
        logger.error(f"删除关键字失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)})

@router.delete("/{rule_id}/replace-rules", response_class=JSONResponse)
async def delete_replace_rules(
    request: Request,
    rule_id: int,
    user = Depends(admin_required)
):
    """从规则中删除替换规则"""
    try:
        payload = await request.json()
        pattern = payload.get('pattern')
        if not pattern:
            return JSONResponse({'success': False, 'error': '未指定要删除的模式'})
            
        result = await container.rule_management_service.delete_replace_rule(rule_id, pattern)
        if result['success']:
            return JSONResponse({'success': True, 'message': '替换规则已删除'})
        else:
            return JSONResponse({'success': False, 'error': result.get('error', '删除失败')})
    except Exception as e:
        logger.error(f"删除替换规则失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)})

