"""
远程配置同步服务
从 ufb/ufb_client.py 迁移并重构
负责通过 WebSocket 与远程服务器同步配置
"""
import asyncio
import json
import os
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    websockets = None
    WEBSOCKETS_AVAILABLE = False

from core.logging import get_logger

logger = get_logger(__name__)

class RemoteConfigSyncService:
    """远程配置同步服务"""
    
    def __init__(self, config_dir: str = "config/remote"):
        # 获取项目根目录
        project_root = Path(os.getcwd())
        self.config_dir = (project_root / config_dir).resolve()
        self.config_path = self.config_dir / "config.json"
        
        self.server_url: Optional[str] = None
        self.token: Optional[str] = None
        self.websocket = None
        self.is_connected = False
        self.on_config_update_callbacks: list[Callable[[Dict[str, Any]], None]] = []
        self.reconnect_task = None
        
        # 确保目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"RemoteConfigSyncService initialized, storage: {self.config_path}")

    def load_local_config(self) -> Dict[str, Any]:
        """加载本地缓存的远程配置"""
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                logger.error("远程配置文件损坏")
                return {}
        return {}

    async def save_config(self, config: Dict[str, Any], sync_to_db: bool = False):
        """保存配置到本地并（可选）同步到数据库"""
        logger.info(f"保存远程配置到本地: {self.config_path}")
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
        
        if sync_to_db:
            await self._sync_to_database(config)

    async def _sync_to_database(self, config: Dict[str, Any]):
        """将配置同步到数据库 (通过 Container)"""
        try:
            from core.container import container
            # 这里需要具体的同步逻辑，目前根据旧代码 ufb_client.py 
            # 逻辑是通过 db_ops.sync_from_json(config)
            # 我们可能需要一个专门的 repo 或 service 来处理这个
            logger.info("同步配置到数据库...")
            # TODO: 实现具体的 DB 同步逻辑
        except Exception as e:
            logger.error(f"同步配置到数据库失败: {e}")

    def merge_configs(self, local_config: Dict[str, Any], cloud_config: Dict[str, Any]) -> Dict[str, Any]:
        """递归合并配置"""
        if not local_config: return cloud_config.copy()
        if not cloud_config: return local_config.copy()

        merged = local_config.copy()
        for key, cloud_value in cloud_config.items():
            if isinstance(cloud_value, dict):
                if key not in merged or not isinstance(merged[key], dict):
                    merged[key] = cloud_value.copy()
                else:
                    merged[key] = self.merge_configs(merged[key], cloud_value)
            elif isinstance(cloud_value, list):
                if key not in merged or not isinstance(merged[key], list):
                    merged[key] = cloud_value.copy()
                else:
                    merged_list = merged[key].copy()
                    for item in cloud_value:
                        if item not in merged_list:
                            merged_list.append(item)
                    merged[key] = merged_list
            else:
                merged[key] = cloud_value
        return merged

    async def connect(self, server_url: str, token: str):
        """连接到远程同步服务器"""
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("websockets 模块不可用，无法启动远程同步")
            return

        self.server_url = server_url
        self.token = token
        
        try:
            full_url = f"{server_url}/ws/config/{token}"
            self.websocket = await websockets.connect(full_url)
            self.is_connected = True
            logger.info(f"已连接到远程同步服务器: {server_url}")
            
            if self.reconnect_task:
                self.reconnect_task.cancel()
                self.reconnect_task = None
                
            # 启动消息处理循环
            asyncio.create_task(self._handle_messages())
            
            # 发送初始同步请求
            local_config = self.load_local_config()
            msg_type = "firstSync" if not local_config else "update"
            await self.websocket.send(json.dumps({
                "type": msg_type,
                **local_config
            }))
            
        except Exception as e:
            logger.error(f"连接远程同步服务器失败: {e}")
            await self._start_reconnect()

    async def _handle_messages(self):
        """处理 WebSocket 消息"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                msg_type = data.get("type")
                logger.info(f"收到服务器同步消息: {msg_type}")

                if msg_type in ("firstSync", "update"):
                    await self.save_config(data, sync_to_db=True)
                elif msg_type == "configConflict":
                    # 总是以云端为准的简单策略
                    await self.websocket.send(json.dumps({
                        "type": "resolveConflict",
                        "choice": "useCloud"
                    }))
                    # 下一条消息通常是全量配置
        except Exception as e:
            logger.error(f"WebSocket 消息处理异常: {e}")
            self.is_connected = False
            await self._start_reconnect()

    async def _start_reconnect(self):
        if not self.reconnect_task or self.reconnect_task.done():
            self.reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self):
        while not self.is_connected and self.server_url:
            logger.info("尝试重新连接远程同步服务器...")
            try:
                await self.connect(self.server_url, self.token)
                break
            except Exception:
                await asyncio.sleep(10)

    async def stop(self):
        if self.websocket:
            await self.websocket.close()
        if self.reconnect_task:
            self.reconnect_task.cancel()
        logger.info("远程配置同步服务已停止")

# 全局单例
remote_config_sync_service = RemoteConfigSyncService()
