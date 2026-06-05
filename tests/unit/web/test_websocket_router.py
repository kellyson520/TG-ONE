"""
Web 模块单元测试 - WebSocket Router

测试 websocket_router.py 中的功能
"""

import pytest
from unittest.mock import AsyncMock, patch


class TestConnectionManager:
    """测试 WebSocket 连接管理器"""
    
    @pytest.fixture
    def connection_manager(self):
        """创建连接管理器实例"""
        from web_admin.routers.websocket_router import ConnectionManager
        return ConnectionManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """模拟 WebSocket 对象"""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.receive_json = AsyncMock()
        ws.close = AsyncMock()
        return ws
    
    @pytest.mark.asyncio
    async def test_connect(self, connection_manager, mock_websocket):
        """测试连接建立"""
        client_id = "test_client_1"
        
        await connection_manager.connect(mock_websocket, client_id)
        
        # 验证连接被接受
        mock_websocket.accept.assert_called_once()
        
        # 验证客户端被添加到活跃连接
        assert client_id in connection_manager.active_connections
        
        # 验证发送了欢迎消息
        mock_websocket.send_json.assert_called_once()
        welcome_msg = mock_websocket.send_json.call_args[0][0]
        assert welcome_msg['type'] == 'connected'
        assert welcome_msg['client_id'] == client_id
    
    @pytest.mark.asyncio
    async def test_disconnect(self, connection_manager, mock_websocket):
        """测试断开连接"""
        client_id = "test_client_2"
        
        # 先连接
        await connection_manager.connect(mock_websocket, client_id)
        assert client_id in connection_manager.active_connections
        
        # 断开
        await connection_manager.disconnect(client_id)
        
        # 验证客户端被移除
        assert client_id not in connection_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_subscribe(self, connection_manager, mock_websocket):
        """测试订阅主题"""
        client_id = "test_client_3"
        await connection_manager.connect(mock_websocket, client_id)
        
        # 订阅有效主题
        success = await connection_manager.subscribe(client_id, "stats")
        assert success is True
        assert client_id in connection_manager.subscriptions["stats"]
        
        # 订阅无效主题
        success = await connection_manager.subscribe(client_id, "invalid_topic")
        assert success is False
    
    @pytest.mark.asyncio
    async def test_unsubscribe(self, connection_manager, mock_websocket):
        """测试取消订阅"""
        client_id = "test_client_4"
        await connection_manager.connect(mock_websocket, client_id)
        await connection_manager.subscribe(client_id, "stats")
        
        # 取消订阅
        success = await connection_manager.unsubscribe(client_id, "stats")
        assert success is True
        assert client_id not in connection_manager.subscriptions["stats"]
    
    @pytest.mark.asyncio
    async def test_send_personal(self, connection_manager, mock_websocket):
        """测试发送私人消息"""
        client_id = "test_client_5"
        await connection_manager.connect(mock_websocket, client_id)
        
        # 重置mock以清除欢迎消息的调用
        mock_websocket.send_json.reset_mock()
        
        # 发送消息
        test_message = {"type": "test", "content": "Hello"}
        await connection_manager.send_personal(client_id, test_message)
        
        # 验证消息被发送
        mock_websocket.send_json.assert_called_once_with(test_message)
    
    @pytest.mark.asyncio
    async def test_broadcast_all(self, connection_manager, mock_websocket):
        """测试广播到所有连接"""
        # 连接多个客户端
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        
        await connection_manager.connect(ws1, "client_1")
        await connection_manager.connect(ws2, "client_2")
        
        # 重置mock
        ws1.send_json.reset_mock()
        ws2.send_json.reset_mock()
        
        # 广播
        test_message = {"type": "broadcast", "data": "test"}
        await connection_manager.broadcast(test_message)
        
        # 验证两个客户端都收到消息
        assert ws1.send_json.called
        assert ws2.send_json.called
    
    @pytest.mark.asyncio
    async def test_broadcast_topic(self, connection_manager):
        """测试广播到特定主题"""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        
        await connection_manager.connect(ws1, "client_1")
        await connection_manager.connect(ws2, "client_2")
        
        # 只有 client_1 订阅 stats
        await connection_manager.subscribe("client_1", "stats")
        
        # 重置mock
        ws1.send_json.reset_mock()
        ws2.send_json.reset_mock()
        
        # 广播到 stats 主题
        await connection_manager.broadcast({"type": "stats_update"}, topic="stats")
        
        # 只有订阅者收到消息
        assert ws1.send_json.called
        assert not ws2.send_json.called
    
    def test_get_stats(self, connection_manager):
        """测试获取统计信息"""
        stats = connection_manager.get_stats()
        
        assert "total_connections" in stats
        assert "subscriptions" in stats
        assert stats["total_connections"] == 0
        assert "stats" in stats["subscriptions"]


class TestBroadcastHelpers:
    """测试广播辅助函数"""
    
    @pytest.mark.asyncio
    async def test_broadcast_stats_update(self):
        """测试广播统计更新"""
        from web_admin.routers.websocket_router import broadcast_stats_update, ws_manager
        
        with patch.object(ws_manager, 'broadcast', new_callable=AsyncMock) as mock_broadcast:
            await broadcast_stats_update({"today_forwards": 100})
            
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args
            assert call_args[0][0]["type"] == "stats_update"
            assert call_args[1]["topic"] == "stats"
    
    @pytest.mark.asyncio
    async def test_broadcast_rule_change(self):
        """测试广播规则变更"""
        from web_admin.routers.websocket_router import broadcast_rule_change, ws_manager
        
        with patch.object(ws_manager, 'broadcast', new_callable=AsyncMock) as mock_broadcast:
            await broadcast_rule_change(1, "updated", {"enabled": True})
            
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args
            assert call_args[0][0]["type"] == "rule_change"
            assert call_args[0][0]["rule_id"] == 1
            assert call_args[0][0]["action"] == "updated"
            assert call_args[1]["topic"] == "rules"
    
    @pytest.mark.asyncio
    async def test_broadcast_system_event(self):
        """测试广播系统事件"""
        from web_admin.routers.websocket_router import broadcast_system_event, ws_manager
        
        with patch.object(ws_manager, 'broadcast', new_callable=AsyncMock) as mock_broadcast:
            await broadcast_system_event("restart", "系统正在重启")
            
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args
            assert call_args[0][0]["type"] == "system_event"
            assert call_args[0][0]["event"] == "restart"
            assert call_args[1]["topic"] == "system"
