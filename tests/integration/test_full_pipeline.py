"""
集成测试: 完整消息处理管道 (修正版)
测试 Loader -> Dedup -> Filter -> AI -> Sender 的完整流程
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from core.pipeline import MessageContext, Pipeline
from middlewares.loader import RuleLoaderMiddleware
from middlewares.dedup import DedupMiddleware
from middlewares.sender import SenderMiddleware
from models.models import ForwardRule, Chat


class TestFullPipelineIntegration:
    """完整管道集成测试"""
    
    @pytest.fixture
    def mock_db(self):
        """模拟数据库"""
        db = AsyncMock()
        db.session = AsyncMock()
        return db
    
    @pytest.fixture
    def mock_client(self):
        """模拟 Telethon 客户端"""
        client = AsyncMock()
        client.send_message = AsyncMock()
        client.send_file = AsyncMock()
        client.forward_messages = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_message(self):
        """模拟消息对象"""
        msg = MagicMock()
        msg.id = 100
        msg.text = "Hello World"
        msg.media = None
        msg.date = datetime.now()
        msg.grouped_id = None
        msg.sender_id = 12345
        return msg
    
    @pytest.fixture
    def create_rule(self):
        """规则工厂函数"""
        def _create(rule_id=1, target_id="222", **kwargs):
            source_chat = MagicMock(spec=Chat)
            source_chat.id = 1
            source_chat.telegram_chat_id = "111"
            
            target_chat = MagicMock(spec=Chat)
            target_chat.id = 2
            target_chat.telegram_chat_id = target_id
            
            rule = MagicMock(spec=ForwardRule)
            rule.id = rule_id
            rule.source_chat = source_chat
            rule.target_chat = target_chat
            rule.enable_dedup = kwargs.get('enable_dedup', False)
            rule.is_replace = kwargs.get('is_replace', False)
            rule.is_ai = kwargs.get('is_ai', False)
            rule.is_original_sender = kwargs.get('is_original_sender', True)
            rule.force_pure_forward = kwargs.get('force_pure_forward', False)
            rule.keywords = kwargs.get('keywords', [])
            rule.replace_rules = kwargs.get('replace_rules', [])
            
            return rule
        return _create
    
    @pytest.mark.asyncio
    async def test_simple_forward_flow(self, mock_client, mock_message, create_rule):
        """测试简单转发流程"""
        rule = create_rule(rule_id=1)
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message
        )
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(DedupMiddleware())
        pipeline.add(SenderMiddleware(mock_bus))
        
        with patch('middlewares.dedup.dedup_service') as mock_dedup:
            mock_dedup.check_and_record = AsyncMock(return_value=(False, None))
            
            with patch('middlewares.sender.forward_messages_queued') as mock_forward:
                mock_forward.return_value = AsyncMock()
                
                await pipeline.execute(ctx)
                
                assert len(ctx.rules) == 1
                mock_rule_repo.get_rules_for_source_chat.assert_called_once_with(111)
                mock_forward.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multi_rule_processing(self, mock_client, mock_message, create_rule):
        """测试多规则处理"""
        rules = [
            create_rule(rule_id=1, target_id="222"),
            create_rule(rule_id=2, target_id="333"),
            create_rule(rule_id=3, target_id="444"),
        ]
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message
        )
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = rules
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(DedupMiddleware())
        pipeline.add(SenderMiddleware(mock_bus))
        
        with patch('middlewares.dedup.dedup_service') as mock_dedup:
            mock_dedup.check_and_record = AsyncMock(return_value=(False, None))
            
            with patch('middlewares.sender.forward_messages_queued') as mock_forward:
                mock_forward.return_value = AsyncMock()
                
                await pipeline.execute(ctx)
                
                assert len(ctx.rules) == 3
                assert mock_forward.call_count == 3
    
    @pytest.mark.asyncio
    async def test_dedup_filtering(self, mock_client, mock_message, create_rule):
        """测试去重过滤"""
        rule = create_rule(rule_id=1, enable_dedup=True)
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message
        )
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(DedupMiddleware())
        pipeline.add(SenderMiddleware(mock_bus))
        
        with patch('middlewares.dedup.dedup_service') as mock_dedup:
            mock_dedup.check_and_record = AsyncMock(return_value=(True, "duplicate_signature"))
            
            with patch('middlewares.sender.forward_messages_queued') as mock_forward:
                await pipeline.execute(ctx)
                
                assert len(ctx.rules) == 0
                mock_forward.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_media_group_handling(self, mock_client, create_rule):
        """测试媒体组处理"""
        messages = []
        for i in range(3):
            msg = MagicMock()
            msg.id = 100 + i
            msg.text = f"Photo {i}"
            msg.media = MagicMock()
            msg.date = datetime.now()
            msg.grouped_id = 999
            messages.append(msg)
        
        rule = create_rule(rule_id=1, is_replace=True)
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=messages[0],
            is_group=True,
            group_messages=messages
        )
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(SenderMiddleware(mock_bus))
        
        await pipeline.execute(ctx)
        
        assert mock_client.send_file.called
    
    @pytest.mark.asyncio
    async def test_error_handling_in_pipeline(self, mock_client, mock_message, create_rule):
        """测试管道中的错误处理"""
        rule = create_rule(rule_id=1)
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message
        )
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(SenderMiddleware(mock_bus))
        
        with patch('middlewares.sender.forward_messages_queued') as mock_forward:
            mock_forward.side_effect = Exception("Network Error")
            
            # SenderMiddleware 会捕获异常并发布 FORWARD_FAILED 事件
            await pipeline.execute(ctx)
            
            # 验证失败事件被发布
            assert mock_bus.publish.called
            failed_event_published = any(
                call[0][0] == "FORWARD_FAILED" 
                for call in mock_bus.publish.call_args_list
            )
            assert failed_event_published
    
    @pytest.mark.asyncio
    async def test_concurrent_rule_execution(self, mock_client, mock_message, create_rule):
        """测试并发规则执行（模拟高负载）"""
        rules = [create_rule(rule_id=i, target_id=f"{200+i}") for i in range(50)]
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=111,
            message_id=100,
            message_obj=mock_message
        )
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = rules
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(SenderMiddleware(mock_bus))
        
        with patch('middlewares.sender.forward_messages_queued') as mock_forward:
            mock_forward.return_value = AsyncMock()
            
            import time
            start = time.time()
            await pipeline.execute(ctx)
            duration = time.time() - start
            
            assert mock_forward.call_count == 50
            assert duration < 5.0
