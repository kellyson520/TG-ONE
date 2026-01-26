import json
import logging
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..models.entry import Entry
from utils.processing.unified_cache import get_smart_cache
from ..core.config import settings

logger = logging.getLogger(__name__)

# 确保数据存储目录存在
def ensure_storage_exists():
    """确保数据存储目录存在"""
    entries_dir = Path(settings.DATA_PATH)
    entries_dir.mkdir(parents=True, exist_ok=True)

# 获取规则对应的条目存储文件路�?
def get_rule_entries_path(rule_id: int) -> Path:
    """获取规则对应的条目存储文件路�?""
    # 使用规则特定的数据目�?
    rule_data_path = settings.get_rule_data_path(rule_id)
    return Path(rule_data_path) / "entries.json"

async def get_entries(rule_id: int, limit: int = 100, offset: int = 0) -> List[Entry]:
    """获取规则对应的条�?""
    try:
        file_path = get_rule_entries_path(rule_id)
        
        # 如果文件不存在，返回空列�?
        if not file_path.exists():
            return []
        
        # 读取文件内容（带 L1/L2 缓存�?
        cache = get_smart_cache("rss.entries", l1_ttl=10, l2_ttl=20)
        cache_key = f"entries:{rule_id}:{file_path.stat().st_mtime_ns}"
        data = cache.get(cache_key)
        if data is None:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            cache.set(cache_key, data)
            
        # 将数据转换为Entry对象
        entries = [Entry(**entry) for entry in data]
        
        # 按发布时间排序（新的在前�?
        entries.sort(key=lambda x: x.published, reverse=True)
        
        # 应用分页
        return entries[offset:offset + limit]
    except Exception as e:
        logger.error(f"获取条目时出�? {str(e)}")
        return []

async def create_entry(entry: Entry) -> bool:
    """创建新条�?""
    try:
        # 设置条目ID和创建时�?
        if not entry.id:
            entry.id = str(uuid.uuid4())
        
        entry.created_at = datetime.now().isoformat()
        
        # 获取规则对应的条�?
        file_path = get_rule_entries_path(entry.rule_id)
        
        entries = []
        # 如果文件已存在，读取现有条目
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as file:
                try:
                    entries = json.load(file)
                except json.JSONDecodeError:
                    logger.warning(f"解析条目文件时出错，将创建新文件: {file_path}")
                    entries = []
        
        # 转换Entry对象为字典并添加到列�?
        entries.append(entry.dict())
        
        # 获取规则的RSS配置，获取最大条目数�?
        try:
            from models.models import get_read_session as get_session, RSSConfig
            session = get_session()
            rss_config = session.query(RSSConfig).filter(RSSConfig.rule_id == entry.rule_id).first()
            max_items = rss_config.max_items if rss_config and hasattr(rss_config, 'max_items') else 50
            session.close()
        except Exception as e:
            logger.warning(f"获取RSS配置失败，使用默认最大条目数�?50): {str(e)}")
            max_items = 50
        
        # 限制条目数量，保留最新的N�?
        if len(entries) > max_items:
            # 按发布时间排序（新的在前�?
            entries.sort(key=lambda x: x.get('published', ''), reverse=True)
            entries = entries[:max_items]
        
        # 保存到文�?
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(entries, file, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"创建条目时出�? {str(e)}")
        return False

async def update_entry(rule_id: int, entry_id: str, updated_data: Dict[str, Any]) -> bool:
    """更新条目"""
    try:
        file_path = get_rule_entries_path(rule_id)
        
        # 如果文件不存在，返回False
        if not file_path.exists():
            return False
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            entries = json.load(file)
        
        # 查找并更新条�?
        found = False
        for i, entry in enumerate(entries):
            if entry.get('id') == entry_id:
                entries[i].update(updated_data)
                found = True
                break
        
        if not found:
            return False
        
        # 保存到文�?
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(entries, file, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"更新条目时出�? {str(e)}")
        return False

async def delete_entry(rule_id: int, entry_id: str) -> bool:
    """删除条目"""
    try:
        file_path = get_rule_entries_path(rule_id)
        
        # 如果文件不存在，返回False
        if not file_path.exists():
            return False
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            entries = json.load(file)
        
        # 查找并删除条�?
        original_length = len(entries)
        entries = [entry for entry in entries if entry.get('id') != entry_id]
        
        if len(entries) == original_length:
            return False  # 没有找到对应ID的条�?
        
        # 保存到文�?
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(entries, file, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"删除条目时出�? {str(e)}")
        return False 