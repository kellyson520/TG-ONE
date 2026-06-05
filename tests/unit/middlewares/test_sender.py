
import pytest
from unittest.mock import MagicMock, AsyncMock
from core.pipeline import MessageContext
from middlewares.sender import SenderMiddleware
from models.models import ForwardRule, Chat
from datetime import datetime

@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Mock send_message and send_file as AsyncMocks
    client.send_message = AsyncMock()
    client.send_file = AsyncMock()
    return client

@pytest.fixture
def mock_message():
    msg = MagicMock()
    msg.id = 100
    msg.text = "Hello World"
    msg.media = None
    msg.date = datetime.now()
    msg.grouped_id = None
    return msg

@pytest.fixture
def mock_rule():
    target_chat = MagicMock(spec=Chat)
    target_chat.id = 2
    target_chat.telegram_chat_id = "222"
    
    rule = MagicMock(spec=ForwardRule)
    rule.id = 5
    rule.target_chat = target_chat
    rule.enable_dedup = False
    rule.is_replace = False
    rule.is_ai = False
    rule.is_original_sender = True
    rule.force_pure_forward = False
    return rule

@pytest.mark.asyncio
async def test_sender_text_message(mock_client, mock_message, mock_rule):
    """测试纯文本消息发送，确保不携带 caption"""
    # 模拟 text-only 模式 (should_copy = True 由于某种规则)
    mock_rule.is_replace = True 
    
    ctx = MessageContext(
        client=mock_client,
        task_id=1,
        chat_id=111,
        message_id=100,
        message_obj=mock_message,
        rules=[mock_rule]
    )
    
    mock_bus = AsyncMock()
    middleware = SenderMiddleware(mock_bus)
    
    next_call = AsyncMock()
    
    # 注入 metadata
    ctx.metadata['modified_text'] = "Modified Content"
    
    await middleware._execute_send(ctx, mock_rule, [100], [ctx])
    
    # 验证 send_message 或 forward 被调用
    mock_client.send_message.assert_called_once()
    args, kwargs = mock_client.send_message.call_args
    assert args[0] == 222 # target_id
    assert args[1] == "Modified Content"
    assert 'caption' not in kwargs

@pytest.mark.asyncio
async def test_sender_media_message(mock_client, mock_message, mock_rule):
    """测试媒体消息发送，确保携带 caption"""
    mock_message.media = MagicMock()
    mock_rule.is_replace = True
    
    ctx = MessageContext(
        client=mock_client,
        task_id=1,
        chat_id=111,
        message_id=100,
        message_obj=mock_message,
        rules=[mock_rule]
    )
    
    mock_bus = AsyncMock()
    middleware = SenderMiddleware(mock_bus)
    next_call = AsyncMock()
    
    await middleware._execute_send(ctx, mock_rule, [100], [ctx])
    
    # 验证 send_file 被调用，且携带 caption 参数
    mock_client.send_file.assert_called_once()
    kwargs = mock_client.send_file.call_args.kwargs
    assert 'caption' in kwargs
    assert kwargs['caption'] == "Hello World"

@pytest.mark.asyncio
async def test_sender_with_buttons(mock_client, mock_message, mock_rule):
    """测试带有按钮的消息发送，验证按钮逻辑"""
    mock_rule.is_replace = True
    ctx = MessageContext(
        client=mock_client,
        task_id=1,
        chat_id=111,
        message_id=100,
        message_obj=mock_message,
        rules=[mock_rule]
    )
    ctx.metadata['buttons'] = [MagicMock()]
    
    # 模拟媒体组情况
    ctx.is_group = True
    ctx.group_messages = [mock_message]
    
    mock_bus = AsyncMock()
    middleware = SenderMiddleware(mock_bus)
    next_call = AsyncMock()
    
    await middleware._execute_send(ctx, mock_rule, [100], [ctx])
    
    # 应该被调用两次：一次 send_file (媒体组), 一次 send_message (按钮)
    assert mock_client.send_file.called
    assert mock_client.send_message.called
    # 验证按钮发送的参数
    args, kwargs = mock_client.send_message.call_args
    assert args[1] == "👇 互动按钮"
    assert 'buttons' in kwargs
