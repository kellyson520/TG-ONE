
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.pipeline import MessageContext
from core.exceptions import TransientError
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
    mock_message.media = MagicMock()
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

@pytest.mark.asyncio
async def test_execute_send_re_raises_transient_error_after_failed_event(mock_client, mock_message, mock_rule):
    """瞬态发送失败必须抛回 worker，否则任务会被误标记完成"""
    mock_rule.is_replace = True
    ctx = MessageContext(
        client=mock_client,
        task_id=1,
        chat_id=111,
        message_id=100,
        message_obj=mock_message,
        rules=[mock_rule]
    )
    ctx.metadata['modified_text'] = "Modified Content"

    mock_bus = AsyncMock()
    middleware = SenderMiddleware(mock_bus)

    with patch("core.helpers.smart_retry.retry_manager.execute", side_effect=TransientError("temporary network error")):
        with pytest.raises(TransientError):
            await middleware._execute_send(ctx, mock_rule, [100], [ctx])

    assert any(
        call.args[0] == "FORWARD_FAILED"
        for call in mock_bus.publish.call_args_list
    )

@pytest.mark.asyncio
async def test_execute_send_wraps_retryable_timeout_as_transient(mock_client, mock_message, mock_rule):
    """SmartRetry 耗尽后抛出的原始网络异常仍应触发 worker 重试"""
    mock_rule.is_replace = True
    ctx = MessageContext(
        client=mock_client,
        task_id=1,
        chat_id=111,
        message_id=100,
        message_obj=mock_message,
        rules=[mock_rule]
    )
    ctx.metadata['modified_text'] = "Modified Content"

    mock_bus = AsyncMock()
    middleware = SenderMiddleware(mock_bus)

    with patch("core.helpers.smart_retry.retry_manager.execute", side_effect=TimeoutError("send timed out")):
        with pytest.raises(TransientError) as exc_info:
            await middleware._execute_send(ctx, mock_rule, [100], [ctx])

    assert isinstance(exc_info.value.__cause__, TimeoutError)
    assert any(
        call.args[0] == "FORWARD_FAILED"
        for call in mock_bus.publish.call_args_list
    )

@pytest.mark.asyncio
async def test_process_re_raises_transient_buffer_failure(mock_client, mock_message, mock_rule):
    """缓冲区直通/推送阶段的瞬态错误也必须交给 worker 重试"""
    mock_rule.enable_only_push = False
    ctx = MessageContext(
        client=mock_client,
        task_id=1,
        chat_id=111,
        message_id=100,
        message_obj=mock_message,
        rules=[mock_rule]
    )
    mock_bus = AsyncMock()
    next_call = AsyncMock()
    middleware = SenderMiddleware(mock_bus)

    with patch("middlewares.sender.smart_buffer.push", side_effect=TransientError("temporary queue pressure")):
        with pytest.raises(TransientError):
            await middleware.process(ctx, next_call)

    next_call.assert_not_called()

@pytest.mark.asyncio
async def test_process_enqueues_multiple_rules_concurrently(mock_client, mock_message, mock_rule):
    """多个目标规则不能因等待 smart buffer flush 而串行阻塞"""
    mock_rule.enable_only_push = False
    second_rule = MagicMock(spec=ForwardRule)
    second_rule.id = 6
    second_rule.target_chat = MagicMock(spec=Chat)
    second_rule.target_chat.telegram_chat_id = "333"
    second_rule.enable_only_push = False

    ctx = MessageContext(
        client=mock_client,
        task_id=1,
        chat_id=111,
        message_id=100,
        message_obj=mock_message,
        rules=[mock_rule, second_rule]
    )
    mock_bus = AsyncMock()
    next_call = AsyncMock()
    middleware = SenderMiddleware(mock_bus)

    first_entered = asyncio.Event()
    first_can_finish = asyncio.Event()
    second_entered = asyncio.Event()

    async def fake_push(rule_id, target_id, context, send_callback):
        if rule_id == mock_rule.id:
            first_entered.set()
            await first_can_finish.wait()
        elif rule_id == second_rule.id:
            second_entered.set()

    with patch("middlewares.sender.smart_buffer.push", side_effect=fake_push):
        process_task = asyncio.create_task(middleware.process(ctx, next_call))
        await asyncio.wait_for(first_entered.wait(), timeout=0.1)
        await asyncio.sleep(0.01)

        try:
            assert second_entered.is_set()
        finally:
            first_can_finish.set()
            await process_task
