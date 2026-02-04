import logging
from __future__ import annotations
import os
import json
import threading
import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from sqlalchemy import select
# from core.container import container (移至内部以避免循环导入)
from models.models import SystemConfiguration

logger = logging.getLogger(__name__)

class _AsyncDbProvider:
    """异步数据库配置提供者"""
    async def get(self, key: str) -> Optional[Any]:
        from core.container import container
        async with container.db.session() as s:
            stmt = select(SystemConfiguration).filter(SystemConfiguration.key == key)
            result = await s.execute(stmt)
            cfg = result.scalar_one_or_none()
            
            if not cfg or cfg.value is None:
                return None
                
            v = cfg.value
            t = (cfg.data_type or 'string').lower()
            
            if t == 'integer':
                try:
                    return int(v)
                except Exception:
                    return None
            if t == 'boolean':
                return str(v).strip().lower() in ('1','true','yes','on')
            if t == 'json':
                try:
                    return json.loads(v)
                except Exception:
                    return None
            return v

    async def set(self, key: str, value: Any, data_type: str = 'string', encrypted: bool = False) -> None:
        v = value
        t = (data_type or 'string').lower()
        if t == 'json':
            v = json.dumps(value, ensure_ascii=False)
        elif t == 'boolean':
            v = 'true' if bool(value) else 'false'
        else:
            v = str(value)
            
        from core.container import container
        async with container.db.session() as s:
            stmt = select(SystemConfiguration).filter(SystemConfiguration.key == key)
            result = await s.execute(stmt)
            cfg = result.scalar_one_or_none()
            
            if not cfg:
                cfg = SystemConfiguration(key=key, value=v, data_type=t, is_encrypted=bool(encrypted))
                s.add(cfg)
            else:
                cfg.value = v
                cfg.data_type = t
                cfg.is_encrypted = bool(encrypted)
            await s.commit()

    async def get_all(self) -> Dict[str, Any]:
        result = {}
        from core.container import container
        async with container.db.session() as s:
            stmt = select(SystemConfiguration)
            rows = (await s.execute(stmt)).scalars().all()
            for cfg in rows:
                result[cfg.key] = cfg.value
        return result

class _JsonProvider:
    def __init__(self, path: str):
        self.path = Path(path)
        self._cache: Dict[str, Any] = {}
        self._loaded = False

    def _load(self):
        if self._loaded: return
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if isinstance(data, dict): self._cache = data
        except Exception:
            self._cache = {}
        self._loaded = True

    def get(self, key: str) -> Optional[Any]:
        self._load()
        return self._cache.get(key)

class ConfigService:
    def __init__(self, json_path: str = './core/config/settings.json'):
        self.db = _AsyncDbProvider()
        self.json = _JsonProvider(json_path)
        # 内存缓存，减少DB调用
        self._memory_cache: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._sync_lock = threading.RLock()
        self._subscribers: Dict[str, Callable[[str, Any], None]] = {}

    async def get(self, key: str, default: Any = None) -> Any:
        """异步获取配置"""
        # 1. 查内存
        if key in self._memory_cache:
            return self._memory_cache[key]
            
        # 2. 查DB (异步)
        v = await self.db.get(key)
        if v is not None:
            self._memory_cache[key] = v
            return v
            
        # 3. 查JSON (同步但快速)
        v = self.json.get(key)
        if v is not None:
            return v
            
        # 4. 查 Settings (替代直接查 Env)
        from core.config import settings
        v = getattr(settings, key, None)
        if v is not None:
             return v
             
        # 5. 最后查 Env (兼容性与测试)
        v = os.getenv(key)
        return v if v is not None else default

    async def set(self, key: str, value: Any, data_type: str = 'string', encrypted: bool = False) -> None:
        """异步设置配置"""
        await self.db.set(key, value, data_type, encrypted)
        self._memory_cache[key] = value
        
        # 通知订阅者
        cb = self._subscribers.get('change')
        if cb:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(key, value)
                else:
                    cb(key, value)
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

    async def get_all(self) -> Dict[str, Any]:
        """获取所有动态配置"""
        return await self.db.get_all()

    async def preload(self):
        """预加载所有配置到内存（应用启动时调用）"""
        try:
            db_configs = await self.db.get_all()
            self._memory_cache.update(db_configs)
        except Exception as e:
            print(f"配置预加载失败: {e}")

    # 保持同步 get 接口以兼容遗留代码（仅查内存/文件/环境变量，不查DB以免阻塞）
    def get_sync(self, key: str, default: Any = None) -> Any:
        if key in self._memory_cache:
            return self._memory_cache[key]
        v = self.json.get(key)
        if v is not None: return v
        from core.config import settings
        v = getattr(settings, key, None)
        if v is not None:
             return v
             
        v = os.getenv(key)
        return v if v is not None else default

    def subscribe_change(self, fn: Callable[[str, Any], None]) -> None:
        with self._sync_lock:
            self._subscribers['change'] = fn

config_service = ConfigService()
