from fastapi import APIRouter, HTTPException, Depends, Body, Request
from fastapi.responses import Response, FileResponse
from typing import Dict, Any
import logging
import os
import json
from pathlib import Path
from ...services.feed_generator import FeedService
from ...models.entry import Entry
from core.config import settings
from core.constants import get_rule_media_dir, get_rule_data_dir
from ...crud.entry import get_entries, create_entry, delete_entry
from core.cache.unified_cache import cached
import mimetypes
from models.models import RSSConfig
from sqlalchemy import select
from core.db_factory import AsyncSessionManager
from datetime import datetime
from ai import get_ai_provider
from models.models import ForwardRule
import re
from models.models import RSSPattern
import shutil
import time
import subprocess
import platform
from pydantic import ValidationError
from core.constants import RSS_MEDIA_BASE_URL

logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_rule_media_path(rule_id: int, filename: str) -> Path:
    """Resolve a public RSS media filename inside the rule media directory."""
    if (
        not filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
        or Path(filename).name != filename
    ):
        raise HTTPException(status_code=400, detail="无效的媒体文件名")

    base_dir = Path(get_rule_media_dir(rule_id)).resolve()
    media_path = (base_dir / filename).resolve()
    try:
        media_path.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的媒体文件路径")

    if media_path.is_dir():
        raise HTTPException(status_code=404, detail="媒体文件未找到")

    return media_path


def _get_rss_public_base_url() -> str:
    if RSS_MEDIA_BASE_URL:
        return RSS_MEDIA_BASE_URL.rstrip("/")
    if settings.RSS_BASE_URL:
        return str(settings.RSS_BASE_URL).rstrip("/")

    scheme = "https" if settings.RSS_PORT == 443 else "http"
    return f"{scheme}://{settings.RSS_HOST}:{settings.RSS_PORT}"


def _safe_headers_for_log(request: Request) -> Dict[str, str]:
    allowed = {"host", "user-agent", "x-forwarded-host", "x-forwarded-proto", "x-real-ip"}
    sensitive = {"authorization", "cookie", "set-cookie", "x-api-key"}
    result = {}
    for key, value in request.headers.items():
        lower = key.lower()
        if lower in sensitive:
            result[key] = "[redacted]"
        elif lower in allowed:
            result[key] = value
    return result


def _rss_local_base_urls() -> set[str]:
    hosts = settings.parse_list_field(settings.WEB_RATE_LIMIT_TRUSTED_IPS)
    if settings.RSS_HOST:
        hosts.append(settings.RSS_HOST)
    return {f"http://{host}:{settings.RSS_PORT}" for host in hosts if host}


def _replace_local_rss_urls(rss_xml: str, base_url: str) -> str:
    for local_base_url in _rss_local_base_urls():
        rss_xml = rss_xml.replace(local_base_url, base_url)
    return rss_xml


# 添加本地访问验证依赖
async def verify_local_access(request: Request):
    """验证请求是否来自本地或Docker内部网络"""
    client_host = request.client.host if request.client else None
    configured_addresses = settings.parse_list_field(settings.WEB_RATE_LIMIT_TRUSTED_IPS)
    local_addresses = {*configured_addresses, "0.0.0.0"}
    if settings.RSS_HOST:
        local_addresses.add(settings.RSS_HOST)
    # 检查是否是Docker内部网络IP (常见的私有网络范围
    docker_ip = False
    if client_host:
        docker_prefixes = ["172.", "192.168.", "10."]
        docker_ip = any(client_host.startswith(prefix) for prefix in docker_prefixes)
    # 如果是本地地址或Docker内部网络IP，允许访问
    if client_host in local_addresses or docker_ip:
        logger.debug(f"已验证访问权 {client_host}")
        return True
    # 拒绝来自外部网络的访问
    logger.warning(f"拒绝来自外部网络的访问 {client_host}")
    raise HTTPException(status_code=403, detail="此API端点仅允许本地或内部网络访问")


@router.get("/")
async def root():
    """服务状态检查"""
    return {"status": "ok", "service": "TG Forwarder RSS"}


@router.get("/rss/feed/{rule_id}")
@cached(cache_name="rss.get_feed", ttl=30)
async def get_feed(rule_id: int, request: Request):
    """返回规则对应的RSS Feed"""
    try:
        # 创建数据库会话
        async with AsyncSessionManager(readonly=True) as session:
            # 查询规则配置
            result = await session.execute(
                select(RSSConfig).filter(RSSConfig.rule_id == rule_id)
            )
            rss_config = result.scalars().first()
            if not rss_config or not rss_config.enable_rss:
                logger.warning(f"规则 {rule_id} 的RSS未启用或不存在")
                raise HTTPException(status_code=404, detail="RSS feed 未启用或不存在")
            base_url = _get_rss_public_base_url()
            logger.debug(f"请求客户 {request.client}")
            logger.info(f"最终使用的媒体基础URL: {base_url}")
        # 获取规则对应的条目
        entries = await get_entries(rule_id)
        logger.info(f"获取 {len(entries)} 个条目")
        # 如果没有条目，返回测试数据
        if not entries:
            logger.warning(f"规则 {rule_id} 没有条目数据，返回测试数据")
            try:
                fg = FeedService.generate_test_feed(rule_id, base_url)
                # 生成 RSS XML
                rss_xml = fg.rss_str(pretty=True)
                # 确保rss_xml是字符串类型
                if isinstance(rss_xml, bytes):
                    logger.info("将RSS XML从字节转换为字符串")
                    rss_xml = rss_xml.decode("utf-8")
                # 记录XML内容的一部分
                xml_sample = rss_xml[:500] + "..." if len(rss_xml) > 500 else rss_xml
                logger.info(f"生成的测试RSS XML (前500字符): {xml_sample}")
                rss_xml = _replace_local_rss_urls(rss_xml, base_url)
                # 确保返回的是字节类型
                if isinstance(rss_xml, str):
                    rss_xml = rss_xml.encode("utf-8")
                return Response(
                    content=rss_xml, media_type="application/xml; charset=utf-8"
                )
            except Exception as e:
                logger.error(f"生成测试Feed时出错 {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500, detail=f"生成测试Feed失败: {str(e)}"
                )
        else:
            # 根据真实数据生成 Feed，传入基础URL
            try:
                fg = await FeedService.generate_feed_from_entries(
                    rule_id, entries, base_url
                )
                # 生成 RSS XML
                rss_xml = fg.rss_str(pretty=True)
                # 确保rss_xml是字符串类型
                if isinstance(rss_xml, bytes):
                    logger.info("将RSS XML从字节转换为字符串")
                    rss_xml = rss_xml.decode("utf-8")
                # 记录XML内容的一部分
                xml_sample = rss_xml[:500] + "..." if len(rss_xml) > 500 else rss_xml
                logger.info(f"生成的RSS XML (前500字符): {xml_sample}")
                rss_xml = _replace_local_rss_urls(rss_xml, base_url)
                # 确保返回的是字节类型
                if isinstance(rss_xml, str):
                    rss_xml = rss_xml.encode("utf-8")
                return Response(
                    content=rss_xml, media_type="application/xml; charset=utf-8"
                )
            except Exception as e:
                logger.error(f"生成真实条目Feed时出错 {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"生成Feed失败: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成RSS feed时出错 {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    pass


@router.get("/media/{rule_id}/{filename}")
async def get_media(rule_id: int, filename: str, request: Request):
    """返回媒体文件"""
    # 记录请求信息
    logger.info(f"媒体请求 - 规则ID: {rule_id}, 文件 {filename}")
    logger.info(f"请求URL: {request.url}")
    logger.info(f"请求头: {_safe_headers_for_log(request)}")
    # 获取基础URL，用于日志记录；不信任 Host/X-Forwarded-Host，避免 RSS 链接投毒
    base_url = _get_rss_public_base_url()
    logger.info(f"最终使用的媒体基础URL: {base_url}")
    # 构建规则特定的媒体文件路
    media_path = _resolve_rule_media_path(rule_id, filename)
    # 记录尝试访问的路
    logger.info(f"尝试访问媒体文件: {media_path}")
    # 检查文件是否存
    if not media_path.exists():
        # 文件不存在，返回404
        logger.error(f"媒体文件未找到 {filename}")
        raise HTTPException(status_code=404, detail=f"媒体文件未找到 {filename}")
    # 确定正确的MIME类型
    mime_type = mimetypes.guess_type(str(media_path))[0]
    if not mime_type:
        # 如果无法确定MIME类型，根据文件扩展名猜测
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext in ["mp4", "mov", "avi", "webm"]:
            mime_type = f"video/{ext}"
        elif ext in ["mp3", "wav", "ogg", "flac"]:
            mime_type = f"audio/{ext}"
        elif ext in ["jpg", "jpeg", "png", "gif"]:
            mime_type = f"image/{ext}"
        else:
            mime_type = "application/octet-stream"
    logger.info(
        f"发送媒体文件 {filename}, MIME类型: {mime_type}, 大小: {os.path.getsize(media_path)} 字节"
    )
    # 返回文件，并设置正确的Content-Type
    return FileResponse(path=media_path, media_type=mime_type, filename=filename)


async def _get_rss_config(rule_id: int):
    """获取RSS配置和最大条目数"""
    async with AsyncSessionManager(readonly=True) as session:
        result = await session.execute(
            select(RSSConfig).filter(RSSConfig.rule_id == rule_id)
        )
        rss_config = result.scalars().first()
    return rss_config, rss_config.max_items


def _validate_media_files(entry_data: Dict[str, Any]):
    """验证媒体文件是否存在，收集文件名"""
    media_filenames = []
    for m in entry_data.get("media", []):
        if isinstance(m, dict):
            media_filenames.append(m.get("filename", "未知"))
            filename = m.get("filename", "")
        else:
            media_filenames.append(getattr(m, "filename", "未知"))
            filename = getattr(m, "filename", "")
        media_path = os.path.join(settings.RSS_MEDIA_DIR, filename)
        if not os.path.exists(media_path):
            logger.warning(f"媒体文件不存 {media_path}")
    return media_filenames


def _delete_entry_media(entry, rule_id: int):
    """删除条目关联的媒体文件"""
    if hasattr(entry, "media") and entry.media:
        logger.info(f"条目 {entry.id} 包含 {len(entry.media)} 个媒体文件，将一并删除")
        media_dir = Path(get_rule_media_dir(rule_id))
        for media in entry.media:
            if hasattr(media, "filename"):
                media_path = media_dir / media.filename
                if media_path.exists():
                    try:
                        os.remove(media_path)
                        logger.info(f"已删除媒体文件 {media_path}")
                    except Exception as e:
                        logger.error(f"删除媒体文件失败: {media_path}, 错误: {str(e)}")


async def _prune_old_entries(rule_id: int, max_items: int):
    """当条目数量接近限制时删除最旧的条目"""
    current_entries = await get_entries(rule_id)
    if len(current_entries) < max_items - 1:
        return
    to_delete_count = len(current_entries) - (max_items - 1)
    if to_delete_count <= 0:
        return
    logger.info(
        f"当前条目数量({len(current_entries)})将超过限制({max_items})，需要删除 {to_delete_count} 个最早的条目"
    )
    sorted_entries = sorted(
        current_entries,
        key=lambda e: (
            datetime.fromisoformat(e.published)
            if hasattr(e, "published")
            else datetime.now()
        ),
    )
    for entry in sorted_entries[:to_delete_count]:
        try:
            _delete_entry_media(entry, rule_id)
            success = await delete_entry(rule_id, entry.id)
            if success:
                logger.info(f"已删除条目 {entry.id}")
            else:
                logger.warning(f"删除条目失败: {entry.id}")
        except Exception as e:
            logger.error(f"处理过期条目时出错 {str(e)}")


async def _apply_ai_extraction(entry, rule_id: int, rss_config):
    """使用AI提取标题和内容"""
    if not rss_config.is_ai_extract:
        return
    try:
        async with AsyncSessionManager(readonly=True) as session:
            result = await session.execute(
                select(ForwardRule).filter(ForwardRule.id == rule_id)
            )
            rule = result.scalars().first()
        provider = await get_ai_provider(rule.ai_model)
        json_text = await provider.process_message(
            message=entry.content or "",
            prompt=rss_config.ai_extract_prompt,
            model=rule.ai_model,
        )
        logger.info(f"AI提取内容: {json_text}")
        if "```" in json_text:
            json_text = re.sub(r"```(\w+)\n", "", json_text)
            json_text = re.sub(r"\n```", "", json_text)
            json_text = json_text.strip()
            logger.info(f"去除代码块标记后的内 {json_text}")
        try:
            json_data = json.loads(json_text)
            logger.info(f"解析后的JSON数据: {json_data}")
            entry.title = json_data.get("title", "")
            entry.content = json_data.get("content", "")
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {str(e)}, 原始文本: {json_text}")
            try:
                json_match = re.search(r"\{.*\}", json_text, re.DOTALL)
                if json_match:
                    clean_json = json_match.group(0)
                    logger.info(f"尝试提取JSON: {clean_json}")
                    json_data = json.loads(clean_json)
                    entry.title = json_data.get("title", "")
                    entry.content = json_data.get("content", "")
                    logger.info(f"成功从文本中提取JSON数据")
                else:
                    logger.error("无法从AI响应中提取有效JSON")
            except Exception as inner_e:
                logger.error(f"尝试二次解析JSON时出 {str(inner_e)}")
        except Exception as e:
            logger.error(f"处理JSON数据时出 {str(e)}")
    except Exception as e:
        logger.error(f"AI提取内容时出 {str(e)}")


async def _apply_custom_patterns(entry, rss_config):
    """应用自定义正则模式提取标题和内容"""
    if not (rss_config.enable_custom_title_pattern or rss_config.enable_custom_content_pattern):
        return
    try:
        original_content = entry.content or ""
        original_title = entry.title

        if rss_config.enable_custom_title_pattern:
            async with AsyncSessionManager(readonly=True) as session:
                result = await session.execute(
                    select(RSSPattern)
                    .filter_by(rss_config_id=rss_config.id, pattern_type="title")
                    .order_by(RSSPattern.priority)
                )
                title_patterns = result.scalars().all()
            logger.info(f"找到 {len(title_patterns)} 个标题模")
            processing_content = original_content
            for pattern in title_patterns:
                logger.info(f"开始尝试标题模 {pattern.pattern}")
                try:
                    match = re.search(pattern.pattern, processing_content)
                    if match and match.groups():
                        entry.title = match.group(1)
                        logger.info(f"使用标题模式 '{pattern.pattern}' 提取到标 {entry.title}")
                    elif match:
                        logger.warning(f"模式 '{pattern.pattern}' 匹配成功但没有捕获组")
                    else:
                        logger.info(f"模式 '{pattern.pattern}' 未找到匹")
                except Exception as e:
                    logger.error(f"应用标题正则表达'{pattern.pattern}' 时出 {str(e)}")
                    logger.exception("详细错误信息:")

        if rss_config.enable_custom_content_pattern:
            async with AsyncSessionManager(readonly=True) as session:
                result = await session.execute(
                    select(RSSPattern)
                    .filter_by(rss_config_id=rss_config.id, pattern_type="content")
                    .order_by(RSSPattern.priority)
                )
                content_patterns = result.scalars().all()
            logger.info(f"找到 {len(content_patterns)} 个内容模")
            processing_content = original_content
            for i, pattern in enumerate(content_patterns):
                try:
                    logger.info(f"[步骤 {i+1}/{len(content_patterns)}] 对内容应用正则表达式: {pattern.pattern}")
                    match = re.search(pattern.pattern, processing_content)
                    if match and match.groups():
                        extracted_content = match.group(1)
                        processing_content = extracted_content
                        entry.content = extracted_content
                        logger.info(f"使用内容模式 '{pattern.pattern}' 提取到内容，长度: {len(extracted_content)}")
                    else:
                        logger.info(f"模式 '{pattern.pattern}' 未找到匹配或没有捕获组，内容保持不变")
                except Exception as e:
                    logger.error(f"应用内容正则表达'{pattern.pattern}' 时出 {str(e)}")

        if not entry.title and original_title:
            entry.title = original_title
            logger.info(f"恢复原标题 {entry.title}")
    except Exception as e:
        logger.error(f"使用正则表达式提取标题和内容时出 {str(e)}")


def _append_sender_info(entry):
    """附加发送者信息到内容"""
    if entry.sender_info:
        entry.sender_info = entry.sender_info.strip()
        entry.content = entry.sender_info + ":" + "\n\n" + entry.content


def _append_original_link(entry):
    """附加原始链接到内容"""
    if not entry.original_link:
        return
    clean_link = entry.original_link.replace("原始消息:", "").strip()
    clean_link = clean_link.replace("\n", "").replace("\r", "")
    clean_link = re.sub(r"\s+", " ", clean_link).strip()
    if clean_link.startswith("http"):
        if entry.author:
            entry.content += f"\n\n[来源: {entry.author}]({clean_link})"
        else:
            entry.content += f"\n\n[来源]({clean_link})"
        logger.info(f"已添加清理后的链接 (Markdown格式)): {clean_link}")
    else:
        logger.warning(f"链接格式不正确，跳过添加: {clean_link}")


@router.post("/api/entries/{rule_id}/add", dependencies=[Depends(verify_local_access)])
async def add_entry(rule_id: int, entry_data: Dict[str, Any] = Body(...)):
    """添加新的条目 (仅限本地访问)"""
    try:
        media_count = len(entry_data.get("media", []))
        has_context = "context" in entry_data and entry_data["context"] is not None
        logger.info(
            f"接收到新条目数据: 规则ID={rule_id}, 标题='{entry_data.get('title', '无标题')}', 媒体数量={media_count}, 包含上下文={has_context}"
        )

        rss_config, max_items = await _get_rss_config(rule_id)

        if media_count > 0:
            _validate_media_files(entry_data)

        if has_context:
            logger.info(
                f"条目包含原始上下文对象，属性: {', '.join(entry_data['context'].keys()) if hasattr(entry_data['context'], 'keys') else '无法获取属性'}"
            )

        entry_data["rule_id"] = rule_id
        if not entry_data.get("message_id"):
            entry_data["message_id"] = entry_data.get("id", "")

        await _prune_old_entries(rule_id, max_items)

        entry = Entry(
            rule_id=rule_id,
            message_id=entry_data.get("message_id", entry_data.get("id", "")),
            title=entry_data.get("title", "新消息息"),
            content=entry_data.get("content", ""),
            published=entry_data.get("published"),
            author=entry_data.get("author", ""),
            link=entry_data.get("link", ""),
            media=entry_data.get("media", []),
            original_link=entry_data.get("original_link"),
            sender_info=entry_data.get("sender_info"),
        )

        await _apply_ai_extraction(entry, rule_id, rss_config)

        logger.info(
            f"启用自定义标题模 {rss_config.enable_custom_title_pattern}, 启用自定义内容模 {rss_config.enable_custom_content_pattern}"
        )
        await _apply_custom_patterns(entry, rss_config)

        _append_sender_info(entry)
        _append_original_link(entry)

        logger.info(f"处理后的消息: {entry.content}")

        success = await create_entry(entry)
        if success:
            return {
                "status": "success",
                "message": f"条目已添加，媒体文件数量: {media_count}",
            }
        else:
            logger.error("添加条目失败")
            raise HTTPException(status_code=500, detail="添加条目失败")
    except ValidationError as e:
        logger.error(f"验证错误: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"添加条目时出 {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/api/entries/{rule_id}/{entry_id}", dependencies=[Depends(verify_local_access)]
)
async def delete_entry_api(rule_id: int, entry_id: str):
    """删除条目 (仅限本地访问)"""
    try:
        # 删除条目
        success = await delete_entry(rule_id, entry_id)
        if not success:
            raise HTTPException(status_code=404, detail="条目未找到到")
        return {"status": "success", "message": "条目已删除"}
    except Exception as e:
        logger.error(f"删除条目时出 {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/entries/{rule_id}")
async def list_entries(rule_id: int, limit: int = 20, offset: int = 0):
    """列出规则对应的所有条目目"""
    try:
        entries = await get_entries(rule_id, limit, offset)
        return {
            "entries": entries,
            "total": len(entries),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"获取条目列表时出 {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/rule/{rule_id}", dependencies=[Depends(verify_local_access)])
async def delete_rule_data(rule_id: int):
    """删除规则相关的所有数据和媒体文件 (仅限本地访问)"""
    try:
        # 获取规则的数据目录和媒体目录
        data_path = Path(get_rule_data_dir(rule_id))
        media_path = Path(get_rule_media_dir(rule_id))
        deleted_files = 0
        deleted_dirs = 0
        failed_paths = []

        # 辅助函数：强制删除目录
        def force_delete_directory(dir_path):
            if not dir_path.exists():
                return True, "目录不存在"
            # 方法1: 使用 shutil.rmtree
            try:
                shutil.rmtree(dir_path, ignore_errors=True)
                if not dir_path.exists():
                    return True, "使用 shutil.rmtree 成功删除"
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            # 方法2: 使用系统命令
            try:
                system = platform.system()
                if system == "Windows":
                    # Windows: 使用 rd /s /q
                    subprocess.run(
                        ["cmd", "/c", "rmdir", "/s", "/q", str(dir_path)],
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                    )
                else:
                    # Linux/Mac: 使用 rm -rf
                    subprocess.run(
                        ["rm", "-rf", str(dir_path)],
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                    )
                if not dir_path.exists():
                    return True, "使用系统命令成功删除"
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            # 方法3: 重命名后删除
            try:
                temp_path = dir_path.parent / f"temp_delete_{time.time()}"
                os.rename(dir_path, temp_path)
                shutil.rmtree(temp_path, ignore_errors=True)
                if not dir_path.exists() and not temp_path.exists():
                    return True, "使用重命名后删除成功"
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            return False, "所有删除方法都失败"

        # 删除媒体目录
        if media_path.exists():
            logger.info(f"开始删除媒体目录 {media_path}")
            success, method = force_delete_directory(media_path)
            if success:
                deleted_dirs += 1
                logger.info(f"已删除媒体目录 {media_path} - {method}")
            else:
                logger.error(f"无法删除媒体目录: {media_path} - {method}")
                failed_paths.append(str(media_path))
        # 删除数据目录
        if data_path.exists():
            logger.info(f"开始删除数据目录 {data_path}")
            success, method = force_delete_directory(data_path)
            if success:
                deleted_dirs += 1
                logger.info(f"已删除数据目录 {data_path} - {method}")
            else:
                logger.error(f"无法删除数据目录: {data_path} - {method}")
                failed_paths.append(str(data_path))
        # 验证删除结果
        remaining_paths = []
        if media_path.exists():
            remaining_paths.append(str(media_path))
        if data_path.exists():
            remaining_paths.append(str(data_path))
        # 返回删除结果
        status = "success" if not remaining_paths else "failed"
        return {
            "status": status,
            "message": f"处理规则 {rule_id} 的数据"
            + ("失败，目录仍然存在" if remaining_paths else "成功，目录已删除"),
            "details": {
                "data_path": str(data_path),
                "media_path": str(media_path),
                "deleted_files": deleted_files,
                "deleted_dirs": deleted_dirs,
                "failed_paths": failed_paths,
                "remaining_paths": remaining_paths,
                "data_dir_exists": data_path.exists(),
                "media_dir_exists": media_path.exists(),
            },
        }
    except Exception as e:
        logger.error(f"删除规则数据时出错 {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除规则数据时出错 {str(e)}")
