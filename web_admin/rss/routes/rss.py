from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from models.models import get_session, get_read_session, User, RSSConfig, ForwardRule, RSSPattern
from repositories.db_operations import DBOperations
from typing import Optional, List
from sqlalchemy.orm import joinedload
from .auth import get_current_user
from feedgen.feed import FeedGenerator
from datetime import datetime
import logging
import base64
import re
from core.helpers.common import get_db_ops
from utils.processing.unified_cache import cached
import os
import aiohttp
from utils.core.constants import RSS_HOST, RSS_PORT, RSS_BASE_URL

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rss")
templates = Jinja2Templates(directory="rss/app/templates")
db_ops = None

async def init_db_ops():
    global db_ops
    if db_ops is None:
        db_ops = await get_db_ops()
    return db_ops

@router.get("/dashboard", response_class=HTMLResponse)
@cached(cache_name="rss.dashboard", ttl=15)
async def rss_dashboard(request: Request, user = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/rss/login", status_code=status.HTTP_302_FOUND)
    
    db_session = get_read_session()
    try:
        # 初始化数据库操作对象
        await init_db_ops()
        
        # 获取所有RSS配置
        rss_configs = db_session.query(RSSConfig).options(
            joinedload(RSSConfig.rule)
        ).all()
        
        # �?RSSConfig 对象转换为字典列�?        configs_list = []
        for config in rss_configs:
            # 处理AI提取提示词，使用Base64编码避免JSON解析问题
            ai_prompt = config.ai_extract_prompt
            ai_prompt_encoded = None
            if ai_prompt:
                # 使用Base64编码处理提示�?                ai_prompt_encoded = base64.b64encode(ai_prompt.encode('utf-8')).decode('utf-8')
                # 添加标记，表示这是Base64编码的内�?                ai_prompt_encoded = "BASE64:" + ai_prompt_encoded
            
            configs_list.append({
                "id": config.id,
                "rule_id": config.rule_id,
                "enable_rss": config.enable_rss,
                "rule_title": config.rule_title,
                "rule_description": config.rule_description,
                "language": config.language,
                "max_items": config.max_items,
                "is_auto_title": config.is_auto_title,
                "is_auto_content": config.is_auto_content,
                "is_ai_extract": config.is_ai_extract,
                "ai_extract_prompt": ai_prompt_encoded,
                "is_auto_markdown_to_html": config.is_auto_markdown_to_html,
                "enable_custom_title_pattern": config.enable_custom_title_pattern,
                "enable_custom_content_pattern": config.enable_custom_content_pattern
            })
        
        # 获取所有转发规则（用于创建新的RSS配置�?        rules = db_session.query(ForwardRule).options(
            joinedload(ForwardRule.source_chat),
            joinedload(ForwardRule.target_chat)
        ).all()
        
        # �?ForwardRule 对象转换为字典列�?        rules_list = []
        for rule in rules:
            rules_list.append({
                "id": rule.id,
                "source_chat": {
                    "id": rule.source_chat.id,
                    "name": rule.source_chat.name
                } if rule.source_chat else None,
                "target_chat": {
                    "id": rule.target_chat.id,
                    "name": rule.target_chat.name
                } if rule.target_chat else None
            })
        
        return templates.TemplateResponse(
            "rss_dashboard.html", 
            {
                "request": request,
                "user": user,
                "rss_configs": configs_list,
                "rules": rules_list,
                "rss_base_url": RSS_BASE_URL or ""
            }
        )
    finally:
        db_session.close()

@router.get("/subscriptions/page", response_class=HTMLResponse)
async def rss_subscriptions_page(request: Request, user = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/rss/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse(
        "rss_subscriptions.html", 
        {
            "request": request,
            "user": user
        }
    )

@router.post("/config", response_class=JSONResponse)
async def rss_config_save(
    request: Request,
    user = Depends(get_current_user),
    config_id: Optional[str] = Form(None),
    rule_id: int = Form(...),
    enable_rss: bool = Form(True),
    rule_title: str = Form(""),
    rule_description: str = Form(""),
    language: str = Form("zh-CN"),
    max_items: int = Form(50),
    is_auto_title: bool = Form(False),
    is_auto_content: bool = Form(False),
    is_ai_extract: bool = Form(False),
    ai_extract_prompt: str = Form(""),
    is_auto_markdown_to_html: bool = Form(False),
    enable_custom_title_pattern: bool = Form(False),
    enable_custom_content_pattern: bool = Form(False)
):
    if not user:
        return JSONResponse(content={"success": False, "message": "未登�?})
    
    # 记录接收到的AI提取提示词内容，帮助调试
    logger.info(f"接收到的AI提取提示词字符数: {len(ai_extract_prompt)}")
    
    # 初始化数据库操作
    await init_db_ops()
    
    db_session = get_read_session()
    try:
        # 创建或更新RSS配置
        # 如果有config_id，表示更�?        if config_id and config_id.strip():
            config_id = int(config_id)
            # 检查配置是否存�?            rss_config = db_session.query(RSSConfig).filter(RSSConfig.id == config_id).first()
            if not rss_config:
                return JSONResponse(content={"success": False, "message": "配置不存�?})
            
            # 更新配置
            rss_config.rule_id = rule_id
            rss_config.enable_rss = enable_rss
            rss_config.rule_title = rule_title
            rss_config.rule_description = rule_description
            rss_config.language = language
            rss_config.max_items = max_items
            rss_config.is_auto_title = is_auto_title
            rss_config.is_auto_content = is_auto_content
            rss_config.is_ai_extract = is_ai_extract
            rss_config.ai_extract_prompt = ai_extract_prompt
            rss_config.is_auto_markdown_to_html = is_auto_markdown_to_html
            rss_config.enable_custom_title_pattern = enable_custom_title_pattern
            rss_config.enable_custom_content_pattern = enable_custom_content_pattern
        else:
            # 检查是否已经存在该规则的配�?            existing_config = db_session.query(RSSConfig).filter(RSSConfig.rule_id == rule_id).first()
            if existing_config:
                return JSONResponse(content={"success": False, "message": "该规则已经存在RSS配置"})
            
            # 创建新配�?            rss_config = RSSConfig(
                rule_id=rule_id,
                enable_rss=enable_rss,
                rule_title=rule_title,
                rule_description=rule_description,
                language=language,
                max_items=max_items,
                is_auto_title=is_auto_title,
                is_auto_content=is_auto_content,
                is_ai_extract=is_ai_extract,
                ai_extract_prompt=ai_extract_prompt,
                is_auto_markdown_to_html=is_auto_markdown_to_html,
                enable_custom_title_pattern=enable_custom_title_pattern,
                enable_custom_content_pattern=enable_custom_content_pattern
            )
        
        # 保存配置
        db_session.add(rss_config)
        db_session.commit()
        
        return JSONResponse({
            "success": True, 
            "message": "RSS 配置已保�?,
            "config_id": rss_config.id,
            "rule_id": rss_config.rule_id
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": f"保存配置失败: {str(e)}"})
    finally:
        db_session.close()

@router.get("/toggle/{rule_id}")
async def toggle_rss(rule_id: int, user = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/rss/login", status_code=status.HTTP_302_FOUND)
    
    db_session = get_read_session()
    try:
        # 初始化数据库操作对象
        db_ops_instance = await init_db_ops()
        
        # 获取配置
        config = await db_ops_instance.get_rss_config(db_session, rule_id)
        if not config:
            return RedirectResponse(
                url="/rss/dashboard?error=配置不存�?, 
                status_code=status.HTTP_302_FOUND
            )
        
        # 切换启用/禁用状�?        await db_ops_instance.update_rss_config(
            db_session,
            rule_id,
            enable_rss=not config.enable_rss
        )
        
        return RedirectResponse(
            url="/rss/dashboard?success=RSS状态已切换", 
            status_code=status.HTTP_302_FOUND
        )
    finally:
        db_session.close()

@router.get("/delete/{rule_id}")
async def delete_rss(rule_id: int, user = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/rss/login", status_code=status.HTTP_302_FOUND)
    
    db_session = get_read_session()
    try:
        # 初始化数据库操作对象
        db_ops_instance = await init_db_ops()
        
        # 删除配置
        config_deleted = await db_ops_instance.delete_rss_config(db_session, rule_id)
        
        if config_deleted:
            # 删除关联的媒体和数据文件
            try:
                logger.info(f"开始删除规�?{rule_id} 的媒体和数据文件")
                # 构建删除API的URL
                rss_url = f"http://{RSS_HOST}:{RSS_PORT}/api/rule/{rule_id}"
                
                # 调用删除API
                async with aiohttp.ClientSession() as client_session:
                    async with client_session.delete(rss_url) as response:
                        if response.status == 200:
                            logger.info(f"成功删除规则 {rule_id} 的媒体和数据文件")
                        else:
                            response_text = await response.text()
                            logger.warning(f"删除规则 {rule_id} 的媒体和数据文件失败, 状态码: {response.status}, 响应: {response_text}")
            except Exception as e:
                logger.error(f"调用删除媒体文件API时出�? {str(e)}")
                # 不影响主流程，继续执�?        
        return RedirectResponse(
            url="/rss/dashboard?success=RSS配置已删�?, 
            status_code=status.HTTP_302_FOUND
        )
    finally:
        db_session.close()

@router.get("/patterns/{config_id}")
async def get_patterns(config_id: int, user = Depends(get_current_user)):
    """获取指定RSS配置的所有模�?""
    if not user:
        return JSONResponse({"success": False, "message": "未登�?}, status_code=status.HTTP_401_UNAUTHORIZED)
    
    db_session = get_read_session()
    try:
        # 初始化数据库操作对象
        db_ops_instance = await init_db_ops()
        
        # 获取所有正则表达式数据
        config = await db_ops_instance.get_rss_config_with_patterns(db_session, config_id)
        if not config:
            return JSONResponse({"success": False, "message": "配置不存�?}, status_code=status.HTTP_404_NOT_FOUND)
        
        # 将模式转换为JSON格式
        patterns = []
        for pattern in config.patterns:
            patterns.append({
                "id": pattern.id,
                "pattern": pattern.pattern,
                "pattern_type": pattern.pattern_type,
                "priority": pattern.priority
            })
        
        return JSONResponse({"success": True, "patterns": patterns})
    finally:
        db_session.close()

@router.post("/pattern")
async def save_pattern(
    request: Request,
    user = Depends(get_current_user),
    pattern_id: Optional[str] = Form(None),
    rss_config_id: int = Form(...),
    pattern: str = Form(...),
    pattern_type: str = Form(...),
    priority: int = Form(0)
):
    """保存模式"""
    logger.info(f"开始保存模式，参数：config_id={rss_config_id}, pattern={pattern}, type={pattern_type}, priority={priority}")
    
    if not user:
        logger.warning("未登录的访问尝试")
        return JSONResponse({"success": False, "message": "未登�?}, status_code=status.HTTP_401_UNAUTHORIZED)
    
    db_session = get_session()
    try:
        # 初始化数据库操作对象
        db_ops_instance = await init_db_ops()
        
        # 检查RSS配置是否存在
        config = await db_ops_instance.get_rss_config(db_session, rss_config_id)
        if not config:
            logger.error(f"RSS配置不存在：config_id={rss_config_id}")
            return JSONResponse({"success": False, "message": "RSS配置不存�?})
        
        logger.debug(f"找到RSS配置：{config}")
    
      
        logger.info("创建新模�?)
        # 创建新模�?        try:
            pattern_obj = await db_ops_instance.create_rss_pattern(
                db_session,
                config.id,
                pattern=pattern,
                pattern_type=pattern_type,
                priority=priority
            )
            logger.info(f"新模式创建成功：{pattern_obj}")
            return JSONResponse({"success": True, "message": "模式已创�?, "pattern_id": pattern_obj.id})
        except Exception as e:
            logger.error(f"创建模式失败：{str(e)}")
            raise
    except Exception as e:
        logger.error(f"保存模式时发生错误：{str(e)}", exc_info=True)
        return JSONResponse({"success": False, "message": f"保存模式失败: {str(e)}"})
    finally:
        db_session.close()

@router.delete("/pattern/{pattern_id}")
async def delete_pattern(pattern_id: int, user = Depends(get_current_user)):
    """删除模式"""
    if not user:
        return JSONResponse({"success": False, "message": "未登�?}, status_code=status.HTTP_401_UNAUTHORIZED)
    
    db_session = get_session()
    try:
        # 初始化数据库操作对象
        await init_db_ops()
        
        # 查询模式
        pattern = db_session.query(RSSPattern).filter(RSSPattern.id == pattern_id).first()
        if not pattern:
            return JSONResponse({"success": False, "message": "找不到该模式"})
        
        # 删除模式
        db_session.delete(pattern)
        db_session.commit()
        
        return JSONResponse({"success": True, "message": "模式删除成功"})
    except Exception as e:
        db_session.rollback()
        logger.error(f"删除模式时出�? {str(e)}")
        return JSONResponse({"success": False, "message": f"删除模式失败: {str(e)}"})
    finally:
        db_session.close()

@router.delete("/patterns/{config_id}")
async def delete_all_patterns(config_id: int, user = Depends(get_current_user)):
    """删除配置的所有模式，通常在更新前调用以便重建模式列表"""
    if not user:
        return JSONResponse({"success": False, "message": "未登�?}, status_code=status.HTTP_401_UNAUTHORIZED)
    
    db_session = get_session()
    try:
        # 初始化数据库操作对象
        await init_db_ops()
        
        # 查询并删除指定配置的所有模�?        patterns = db_session.query(RSSPattern).filter(RSSPattern.rss_config_id == config_id).all()
        count = len(patterns)
        for pattern in patterns:
            db_session.delete(pattern)
        
        db_session.commit()
        logger.info(f"已删除配�?{config_id} 的所有模式，�?{count} �?)
        
        return JSONResponse({"success": True, "message": f"已删�?{count} 个模�?})
    except Exception as e:
        db_session.rollback()
        logger.error(f"删除配置 {config_id} 的所有模式时出错: {str(e)}")
        return JSONResponse({"success": False, "message": f"删除所有模式失�? {str(e)}"})
    finally:
        db_session.close()

@router.post("/test-regex")
async def test_regex(user = Depends(get_current_user), 
                    pattern: str = Form(...), 
                    test_text: str = Form(...), 
                    pattern_type: str = Form(...)):
    """测试正则表达式匹配结�?""
    if not user:
        return JSONResponse({"success": False, "message": "未登�?}, status_code=status.HTTP_401_UNAUTHORIZED)
    
    try:
        
        
        # 记录测试信息
        logger.info(f"测试正则表达�? {pattern}")
        logger.info(f"测试类型: {pattern_type}")
        logger.info(f"测试文本长度: {len(test_text)} 字符")
        
        # 执行正则匹配
        match = re.search(pattern, test_text)
        
        # 检查是否有匹配
        if not match:
            return JSONResponse({
                "success": True,
                "matched": False,
                "message": "未找到匹�?
            })
            
        # 检查捕获组
        if not match.groups():
            return JSONResponse({
                "success": True,
                "matched": True,
                "has_groups": False,
                "message": "匹配成功，但没有捕获组。请使用括号 () 来创建捕获组�?
            })
            
        # 成功匹配且有捕获�?        extracted_content = match.group(1)
        
        # 返回匹配结果
        return JSONResponse({
            "success": True,
            "matched": True,
            "has_groups": True,
            "extracted": extracted_content,
            "message": "匹配成功�?
        })
        
    except Exception as e:
        logger.error(f"测试正则表达式时出错: {str(e)}")
        return JSONResponse({
            "success": False,
            "message": f"测试失败: {str(e)}"
        }) 