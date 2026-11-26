"""
WebSocket Router - 实时数据推送

提供 WebSocket 端点用于：
- 转发统计实时更新
- 规则状态变更通知
- 系统事件广播
- 日志推送
- 告警通知

Phase G.3: 增强广播智能化
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set, List, Optional, Any
import asyncio
import json
import logging
import time
from datetime import datetime
from collections import defaultdict


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


class ConnectionManager:
    """WebSocket 连接管理器 (增强版)"""
    
    # 节流间隔 (毫秒)
    THROTTLE_MS = 100
    
    def __init__(self):
        # 存储活跃连接 {client_id: websocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # 主题订阅 {topic: set(client_ids)}
        self.subscriptions: Dict[str, Set[str]] = {
            "stats": set(),         # 统计数据更新
            "rules": set(),         # 规则状态变更
            "system": set(),        # 系统事件
            "logs": set(),          # 日志推送
            "alerts": set(),        # 告警通知 (新增)
            "notifications": set(), # 用户通知 (新增)
        }
        self._lock = asyncio.Lock()
        
        # 节流状态 {topic: {"last_time": float, "pending": list}}
        self._throttle_state: Dict[str, dict] = defaultdict(lambda: {"last_time": 0, "pending": []})
        self._throttle_tasks: Dict[str, Optional[asyncio.Task]] = defaultdict(lambda: None)
        
        # 统计
        self._stats = {
            "total_broadcasts": 0,
            "throttled_count": 0,
            "messages_merged": 0
        }
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """建立连接"""
        await websocket.accept()
        async with self._lock:
            self.active_connections[client_id] = websocket
        logger.info(f"WebSocket 客户端连接: {client_id}")
        
        # 发送欢迎消息
        await self.send_personal(client_id, {
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat(),
            "available_topics": list(self.subscriptions.keys())
        })
    
    async def disconnect(self, client_id: str):
        """断开连接"""
        async with self._lock:
            if client_id in self.active_connections:
                del self.active_connections[client_id]
            # 从所有订阅中移除
            for topic in self.subscriptions.values():
                topic.discard(client_id)
        logger.info(f"WebSocket 客户端断开: {client_id}")
    
    async def subscribe(self, client_id: str, topic: str) -> bool:
        """订阅主题"""
        if topic not in self.subscriptions:
            return False
        async with self._lock:
            self.subscriptions[topic].add(client_id)
        logger.debug(f"客户端 {client_id} 订阅主题: {topic}")
        return True
    
    async def unsubscribe(self, client_id: str, topic: str) -> bool:
        """取消订阅"""
        if topic not in self.subscriptions:
            return False
        async with self._lock:
            self.subscriptions[topic].discard(client_id)
        return True
    
    async def send_personal(self, client_id: str, message: dict):
        """发送私人消息"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"发送消息失败 [{client_id}]: {e}")
                await self.disconnect(client_id)
    
    async def broadcast(self, message: dict, topic: Optional[str] = None, throttle: bool = False):
        """
        广播消息到所有连接或特定主题订阅者
        
        Args:
            message: 消息内容
            topic: 目标主题
            throttle: 是否启用节流 (高频事件推荐开启)
        """
        message["timestamp"] = datetime.utcnow().isoformat()
        
        if throttle and topic:
            await self._throttled_broadcast(message, topic)
        else:
            await self._immediate_broadcast(message, topic)
    
    async def _throttled_broadcast(self, message: dict, topic: str):
        """节流广播 (100ms 内合并)"""
        state = self._throttle_state[topic]
        now = time.time() * 1000  # 毫秒
        
        async with self._lock:
            if now - state["last_time"] < self.THROTTLE_MS:
                # 在节流窗口内，缓存消息
                state["pending"].append(message)
                self._stats["messages_merged"] += 1
                
                # 如果没有定时器，启动一个
                if self._throttle_tasks[topic] is None or self._throttle_tasks[topic].done():
                    delay = (self.THROTTLE_MS - (now - state["last_time"])) / 1000
                    from services.exception_handler import exception_handler
                    self._throttle_tasks[topic] = exception_handler.create_task(
                        self._flush_pending(topic, delay),
                        name=f"ws_throttle_{topic}"
                    )
                return
        
        # 立即广播
        await self._immediate_broadcast(message, topic)
        state["last_time"] = now
    
    async def _flush_pending(self, topic: str, delay: float):
        """延迟后刷新待发送消息"""
        await asyncio.sleep(delay)
        
        state = self._throttle_state[topic]
        async with self._lock:
            if not state["pending"]:
                return
            
            # 合并消息
            merged = self._merge_messages(topic, state["pending"])
            state["pending"].clear()
            state["last_time"] = time.time() * 1000
        
        await self._immediate_broadcast(merged, topic)
        self._stats["throttled_count"] += 1
    
    def _merge_messages(self, topic: str, messages: List[dict]) -> dict:
        """合并多条消息"""
        if len(messages) == 1:
            return messages[0]
        
        return {
            "type": "batch",
            "topic": topic,
            "count": len(messages),
            "items": messages[-10:],  # 最多保留 10 条
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _immediate_broadcast(self, message: dict, topic: Optional[str] = None):
        """立即广播"""
        if topic:
            # 仅发送给订阅了该主题的客户端
            subscribers = self.subscriptions.get(topic, set())
            targets = [cid for cid in subscribers if cid in self.active_connections]
        else:
            # 发送给所有连接
            targets = list(self.active_connections.keys())
        
        disconnected = []
        for client_id in targets:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"广播失败 [{client_id}]: {e}")
                disconnected.append(client_id)
        
        # 清理断开的连接
        for client_id in disconnected:
            await self.disconnect(client_id)
        
        self._stats["total_broadcasts"] += 1
    
    def get_stats(self) -> dict:
        """获取连接统计"""
        return {
            "total_connections": len(self.active_connections),
            "subscriptions": {
                topic: len(subs) for topic, subs in self.subscriptions.items()
            },
            "broadcast_stats": self._stats.copy()
        }


# 全局连接管理器实例
ws_manager = ConnectionManager()


@router.websocket("/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 实时数据端点
    
    客户端连接后可以发送以下命令：
    - {"action": "subscribe", "topic": "stats"}  订阅主题
    - {"action": "unsubscribe", "topic": "stats"} 取消订阅
    - {"action": "ping"}  心跳检测
    """
    # 生成客户端ID
    client_id = f"client_{id(websocket)}_{datetime.utcnow().timestamp()}"
    
    try:
        await ws_manager.connect(websocket, client_id)
        
        # 默认订阅统计更新
        await ws_manager.subscribe(client_id, "stats")
        
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_json()
                action = data.get("action")
                
                if action == "subscribe":
                    topic = data.get("topic")
                    success = await ws_manager.subscribe(client_id, topic)
                    await ws_manager.send_personal(client_id, {
                        "type": "subscription",
                        "topic": topic,
                        "success": success
                    })
                
                elif action == "unsubscribe":
                    topic = data.get("topic")
                    success = await ws_manager.unsubscribe(client_id, topic)
                    await ws_manager.send_personal(client_id, {
                        "type": "unsubscription",
                        "topic": topic,
                        "success": success
                    })
                
                elif action == "ping":
                    await ws_manager.send_personal(client_id, {
                        "type": "pong"
                    })
                
                else:
                    await ws_manager.send_personal(client_id, {
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    })
                    
            except json.JSONDecodeError:
                await ws_manager.send_personal(client_id, {
                    "type": "error",
                    "message": "Invalid JSON format"
                })
                
    except WebSocketDisconnect:
        await ws_manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket 错误 [{client_id}]: {e}")
        await ws_manager.disconnect(client_id)


@router.get("/stats")
async def get_websocket_stats():
    """获取 WebSocket 连接统计"""
    return ws_manager.get_stats()


# ========== 事件广播辅助函数 ==========

async def broadcast_stats_update(stats: dict, throttle: bool = True):
    """广播统计数据更新"""
    await ws_manager.broadcast({
        "type": "stats_update",
        "data": stats
    }, topic="stats", throttle=throttle)


async def broadcast_rule_change(rule_id: int, action: str, details: dict = None):
    """广播规则状态变更"""
    await ws_manager.broadcast({
        "type": "rule_change",
        "rule_id": rule_id,
        "action": action,  # created, updated, deleted, toggled
        "details": details or {}
    }, topic="rules")


async def broadcast_system_event(event_type: str, message: str, data: dict = None):
    """广播系统事件"""
    await ws_manager.broadcast({
        "type": "system_event",
        "event": event_type,
        "message": message,
        "data": data or {}
    }, topic="system")


async def broadcast_log(level: str, message: str, module: str = None, throttle: bool = True):
    """广播日志消息"""
    await ws_manager.broadcast({
        "type": "log",
        "level": level,
        "message": message,
        "module": module
    }, topic="logs", throttle=throttle)


async def broadcast_alert(alert_type: str, title: str, message: str, severity: str = "warning"):
    """广播告警通知"""
    await ws_manager.broadcast({
        "type": "alert",
        "alert_type": alert_type,
        "title": title,
        "message": message,
        "severity": severity  # info, warning, error, critical
    }, topic="alerts")


async def broadcast_notification(user_id: Optional[int], title: str, body: str, action_url: str = None):
    """广播用户通知"""
    await ws_manager.broadcast({
        "type": "notification",
        "user_id": user_id,  # None = 全体通知
        "title": title,
        "body": body,
        "action_url": action_url
    }, topic="notifications")


# ========== EventBus 集成 ==========

async def broadcast_event(event_name: str, event_data: Any):
    """
    EventBus 事件钩子: 自动广播事件到 WebSocket
    
    事件名称到 topic 的映射:
    - FORWARD_*, STATS_* -> stats
    - LOG_* -> logs
    - ALERT_*, ERROR_* -> alerts
    - NOTIFICATION_*, NOTIFY_* -> notifications
    - 其他 -> system
    """
    event_upper = event_name.upper()
    
    if event_upper.startswith("FORWARD_") or event_upper.startswith("STATS_"):
        topic = "stats"
        throttle = True
    elif event_upper.startswith("LOG_"):
        topic = "logs"
        throttle = True
    elif event_upper.startswith("ALERT_") or event_upper.startswith("ERROR_"):
        topic = "alerts"
        throttle = False
    elif event_upper.startswith("NOTIFICATION_") or event_upper.startswith("NOTIFY_"):
        topic = "notifications"
        throttle = False
    else:
        topic = "system"
        throttle = False
    
    await ws_manager.broadcast({
        "type": "event",
        "event": event_name,
        "data": event_data
    }, topic=topic, throttle=throttle)

