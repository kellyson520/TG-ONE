import os
from typing import Dict, List, Optional, Any
from core.config import settings
from core.helpers.json_utils import json_loads, json_dumps
from core.logging import get_logger
import aiofiles
from pathlib import Path

logger = get_logger(__name__)

class HotwordRepository:
    """
    热词持久化层：专门负责与文件系统交互。
    遵循 Standard_Whitepaper.md 的 Repository 规则。
    """
    
    def __init__(self):
        self.base_dir = settings.HOT_DIR
        self.config_dir = self.base_dir / "config"
        self._ensure_directories()
        self._ensure_default_configs()
        
    def _ensure_directories(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
    def _ensure_default_configs(self):
        """确保核心配置文件存在，避免读取时报错"""
        defaults = {
            "black": {"terms": {}},
            "white": {"terms": {}},
            "noise": []
        }
        for name, content in defaults.items():
            path = self.config_dir / f"{name}.json"
            if not path.exists():
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(json_dumps(content))
        
    async def save_temp_counts(self, channel: str, counts: Dict[str, Dict[str, int]]):
        """
        异步增量保存数据。
        counts 格式: { word: {"f": frequency, "u": user_increment} }
        """
        chan_dir = self.base_dir / channel
        chan_dir.mkdir(parents=True, exist_ok=True)
        temp_file = chan_dir / f"{channel}_temp.json"
        
        existing = {}
        if temp_file.exists():
            try:
                async with aiofiles.open(temp_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content:
                        existing = json_loads(content)
            except Exception as e:
                logger.log_error(f"读取热词临时文件 {channel}", e, details=f"Path: {temp_file}")
        
        for word, meta in counts.items():
            current = existing.get(word, {"f": 0, "u": 0})
            if isinstance(current, (int, float)): # 兼容旧格式
                current = {"f": int(current), "u": 1}
            
            existing[word] = {
                "f": current.get("f", 0) + meta.get("f", 0),
                "u": current.get("u", 0) + meta.get("u", 0)
            }
        
        try:
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json_dumps(existing))
        except Exception as e:
             logger.log_error(f"保存热词临时文件 {channel}", e, details=f"Path: {temp_file}")

    def load_rankings(self, channel: str, filename: str) -> Dict[str, int]:
        """读取榜单数据"""
        file_path = self.base_dir / channel / filename
        if not file_path.exists():
            return {}
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return json_loads(content) if content else {}
        except Exception as e:
            logger.log_error("加载热词榜单", e, details=f"Path: {file_path}")
            return {}

    def get_channel_dirs(self) -> List[str]:
        """获取所有有数据的频道"""
        if not self.base_dir.exists(): return []
        return [d for d in os.listdir(self.base_dir) 
                if (self.base_dir / d).is_dir() and d != "config"]

    def load_config(self, name: str) -> Dict[str, float]:
        """加载黑/白名单/特征库配置"""
        file_path = self.config_dir / f"{name}.json"
        if not file_path.exists():
            return {}
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content: return {}
                data = json_loads(content)
                # 兼容 列表格式 或 字典格式
                if isinstance(data, list):
                    return {k: 1.0 for k in data}
                return {k: float(v) for k, v in data.get("terms", {}).items()}
        except Exception as e:
            logger.log_error(f"加载热词配置 {name}", e, details=f"Path: {file_path}")
            return {}

    async def save_config(self, name: str, data: Any):
        """保存配置到磁盘"""
        file_path = self.config_dir / f"{name}.json"
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                if isinstance(data, (list, set)):
                    # 特征库通常存为列表
                    await f.write(json_dumps(list(data)))
                else:
                    # 权重库存为固定格式字典
                    await f.write(json_dumps({"terms": data}))
            return True
        except Exception as e:
            logger.log_error(f"保存热词配置 {name}", e, details=f"Path: {file_path}")
            return False

    async def atomic_rename(self, src: Path, dst: Path):
        """原子重命名"""
        try:
            if src.exists():
                src.rename(dst)
                return True
        except Exception as e:
            logger.log_error("热词文件原子重命名失败", e, details=f"Src: {src} -> Dst: {dst}")
        return False
