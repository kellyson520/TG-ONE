"""
边界条件与异常场景测试
测试各种异常情况和边界条件
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from core.pipeline import MessageContext, Pipeline
from middlewares.loader import RuleLoaderMiddleware
from middlewares.sender import SenderMiddleware
from services.queue_service import FloodWaitException


class TestEdgeCasesAndExceptions:
    """边界条件与异常测试"""
    
    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.send_message = AsyncMock()
        client.send_file = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_message(self):
        msg = MagicMock()
        msg.id = 100
        msg.text = "Test"
        msg.media = None
        msg.date = datetime.now()
        msg.grouped_id = None
        return msg
    
    @pytest.mark.asyncio
    async def test_empty_rules_list(self, mock_client, mock_message):
        """测试空规则列表"""
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message
        )
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = []
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(SenderMiddleware(mock_bus))
        
        # 应该正常完成，不发送任何消息
        await pipeline.execute(ctx)
        
        assert len(ctx.rules) == 0
        assert not ctx.is_terminated
    
    @pytest.mark.asyncio
    async def test_flood_wait_exception(self, mock_client, mock_message):
        """测试 FloodWait 异常处理"""
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "222"
        rule.enable_dedup = False
        rule.is_replace = False
        rule.force_pure_forward = False
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message,
            rules=[rule]
        )
        
        mock_bus = AsyncMock()
        middleware = SenderMiddleware(mock_bus)
        
        with patch('middlewares.sender.forward_messages_queued') as mock_forward:
            # 模拟 FloodWait
            mock_forward.side_effect = FloodWaitException(30)
            
            # 应该抛出异常
            with pytest.raises(FloodWaitException) as exc_info:
                await middleware.process(ctx, AsyncMock())
            
            assert exc_info.value.seconds == 30
    
    @pytest.mark.asyncio
    async def test_none_message_text(self, mock_client):
        """测试消息文本为 None 的情况"""
        msg = MagicMock()
        msg.id = 100
        msg.text = None  # 无文本
        msg.media = None
        msg.date = datetime.now()
        
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "222"
        rule.is_replace = True  # 触发 copy 模式
        rule.enable_dedup = False
        rule.is_ai = False
        rule.force_pure_forward = False
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=msg,
            rules=[rule]
        )
        
        mock_bus = AsyncMock()
        middleware = SenderMiddleware(mock_bus)
        
        await middleware.process(ctx, AsyncMock())
        
        # 应该发送空字符串
        mock_client.send_message.assert_called_once()
        args = mock_client.send_message.call_args[0]
        assert args[1] == ""  # 空文本
    
    @pytest.mark.asyncio
    async def test_very_long_text_message(self, mock_client):
        """测试超长文本消息"""
        # Telegram 限制单条消息 4096 字符
        long_text = "A" * 10000
        
        msg = MagicMock()
        msg.id = 100
        msg.text = long_text
        msg.media = None
        msg.date = datetime.now()
        
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "222"
        rule.is_replace = True
        rule.enable_dedup = False
        rule.is_ai = False
        rule.force_pure_forward = False
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=msg,
            rules=[rule]
        )
        
        mock_bus = AsyncMock()
        middleware = SenderMiddleware(mock_bus)
        
        await middleware.process(ctx, AsyncMock())
        
        # 验证发送被调用（实际应用中可能需要分段发送）
        assert mock_client.send_message.called
    
    @pytest.mark.asyncio
    async def test_special_characters_in_text(self, mock_client):
        """测试特殊字符处理"""
        special_text = "Test\n\r\t<>&\"'`\\|{}[]"
        
        msg = MagicMock()
        msg.id = 100
        msg.text = special_text
        msg.media = None
        msg.date = datetime.now()
        
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "222"
        rule.is_replace = True
        rule.enable_dedup = False
        rule.is_ai = False
        rule.force_pure_forward = False
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=msg,
            rules=[rule]
        )
        
        mock_bus = AsyncMock()
        middleware = SenderMiddleware(mock_bus)
        
        await middleware.process(ctx, AsyncMock())
        
        # 验证特殊字符被正确传递
        args = mock_client.send_message.call_args[0]
        assert special_text in args[1]
    
    @pytest.mark.asyncio
    async def test_media_group_with_empty_list(self, mock_client, mock_message):
        """测试空媒体组列表"""
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "222"
        rule.is_replace = True
        rule.enable_dedup = False
        rule.is_ai = False
        rule.force_pure_forward = False
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message,
            rules=[rule],
            is_group=True,
            group_messages=[]  # 空列表
        )
        
        mock_bus = AsyncMock()
        middleware = SenderMiddleware(mock_bus)
        
        await middleware.process(ctx, AsyncMock())
        
        # 应该回退到普通文本发送
        assert mock_client.send_message.called
    
    @pytest.mark.asyncio
    async def test_concurrent_event_bus_publish(self, mock_client, mock_message):
        """测试并发事件发布"""
        rules = [MagicMock() for _ in range(10)]
        for i, rule in enumerate(rules):
            rule.id = i
            rule.target_chat = MagicMock()
            rule.target_chat.telegram_chat_id = f"{200+i}"
            rule.enable_dedup = False
            rule.is_replace = False
            rule.force_pure_forward = False
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message,
            rules=rules
        )
        
        mock_bus = AsyncMock()
        middleware = SenderMiddleware(mock_bus)
        
        with patch('middlewares.sender.forward_messages_queued') as mock_forward:
            mock_forward.return_value = AsyncMock()
            
            await middleware.process(ctx, AsyncMock())
            
            # 验证所有事件都被发布
            assert mock_bus.publish.call_count >= 10
    
    @pytest.mark.asyncio
    async def test_invalid_target_chat_id(self, mock_client, mock_message):
        """测试无效的目标聊天ID"""
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "invalid_id"  # 无效ID
        rule.enable_dedup = False
        rule.is_replace = False
        rule.force_pure_forward = False
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message,
            rules=[rule]
        )
        
        mock_bus = AsyncMock()
        middleware = SenderMiddleware(mock_bus)
        
        with patch('middlewares.sender.forward_messages_queued') as mock_forward:
            mock_forward.side_effect = ValueError("Invalid chat ID")
            
            # 应该捕获异常并发布失败事件
            with pytest.raises(ValueError):
                await middleware.process(ctx, AsyncMock())
    
    @pytest.mark.asyncio
    async def test_metadata_edge_cases(self, mock_client, mock_message):
        """测试元数据边界情况"""
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "222"
        rule.is_replace = True
        rule.enable_dedup = False
        rule.is_ai = False
        rule.force_pure_forward = False
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message,
            rules=[rule]
        )
        
        # 测试各种元数据组合
        test_cases = [
            {},  # 空元数据
            {'modified_text': None},  # None 值
            {'modified_text': ''},  # 空字符串
            {'buttons': None},  # None 按钮
            {'buttons': []},  # 空按钮列表
            {'reply_to_msg_id': 0},  # 无效回复ID
        ]
        
        mock_bus = AsyncMock()
        middleware = SenderMiddleware(mock_bus)
        
        for metadata in test_cases:
            ctx.metadata = metadata
            await middleware.process(ctx, AsyncMock())
            
        # 所有情况都应该成功处理
        assert mock_client.send_message.call_count == len(test_cases)
