"""
集成测试: 消息处理流程 (Message Logic Integration)
测试从消息输入到过滤器链、数据库交互、最终转发行为的完整逻辑。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from handlers.user_handler import process_forward_rule
from models.models import ForwardRule, Chat, ForwardMode, Keyword
from core.helpers.forward_recorder import forward_recorder
from sqlalchemy import select

from sqlalchemy.orm import selectinload

@pytest.mark.asyncio
async def test_integration_flow_success(db, clear_data):
    """
    测试完整转发流程:
    Rule(Keyword 'test') -> Message('test') -> Filter Matches -> Client.forward -> DB Record
    """
    # 1. 准备数据 (Real DB Setup)
    # Create Source & Target Chats
    source_chat = Chat(telegram_chat_id="111111", name="Source", chat_type="user")
    target_chat = Chat(telegram_chat_id="987654321", name="Integration Target", chat_type="group")
    db.add(source_chat)
    db.add(target_chat)
    await db.commit()
    
    # Create Rule
    rule = ForwardRule(
        source_chat_id=source_chat.id,
        target_chat_id=target_chat.id,
        forward_mode=ForwardMode.WHITELIST,
        enable_rule=True,
        force_pure_forward=True,
    )
    db.add(rule)
    await db.commit()
    
    # Add Keyword
    kw = Keyword(rule_id=rule.id, keyword="magic", is_blacklist=False)
    db.add(kw)
    await db.commit()
    
    # Reload Rule with Keywords Eager Loaded
    stmt = select(ForwardRule).where(ForwardRule.id == rule.id).options(selectinload(ForwardRule.keywords))
    result = await db.execute(stmt)
    rule_loaded = result.scalar_one()
    
    # 2. 准备依赖 (Real Logic, Mock I/O)
    mock_client = MagicMock()
    mock_client.forward_messages = AsyncMock(return_value=MagicMock(id=8888))
    
    mock_event = MagicMock()
    mock_event.message.text = "This contains magic keyword"
    mock_event.message.chat_id = 987654321 
    mock_event.chat_id = 111111 
    mock_event.sender.id = 12345
    mock_event.message.grouped_id = None
    
    # Debug verification
    assert len(rule_loaded.keywords) == 1

    # 3. 执行
    await process_forward_rule(mock_client, mock_event, mock_event.chat_id, rule_loaded)
    
    # 4. 验证行为
    mock_client.forward_messages.assert_awaited()
    args = mock_client.forward_messages.await_args
    # Verify kwargs 'entity' or 'to_peer'
    kwargs = args[1]
    assert kwargs.get('entity') == 987654321 or kwargs.get('to_peer') == 987654321

@pytest.mark.asyncio
async def test_integration_flow_filtered(db, clear_data):
    """
    测试被过滤流程:
    Rule(Keyword 'magic') -> Message('boring') -> Filter Block -> No Client Call
    """
    # Setup
    target_chat = Chat(telegram_chat_id="999", name="T", chat_type="group")
    source_chat = Chat(telegram_chat_id="222", name="S", chat_type="group")
    db.add(target_chat)
    db.add(source_chat)
    await db.commit()
    
    rule = ForwardRule(
        source_chat_id=source_chat.id,
        target_chat_id=target_chat.id,
        forward_mode=ForwardMode.WHITELIST,
        enable_rule=True
    )
    db.add(rule)
    await db.commit()
    
    kw = Keyword(rule_id=rule.id, keyword="magic", is_blacklist=False)
    db.add(kw)
    await db.commit()
    await db.refresh(rule)
    
    mock_client = MagicMock()
    mock_client.forward_messages = AsyncMock()
    
    mock_event = MagicMock()
    mock_event.message.text = "This is boring text"
    mock_event.chat_id = 222
    mock_event.message.grouped_id = None
    
    await process_forward_rule(mock_client, mock_event, 222, rule)
    
    # Verify NOT called
    mock_client.forward_messages.assert_not_called()

@pytest.mark.asyncio
async def test_integration_flow_fallback(db, clear_data):
    """
    测试降级机制:
    当过滤器链抛出异常时，应自动切换到 _fallback_process_forward_rule 执行转发
    """
    # 1. 准备数据
    target_chat = Chat(telegram_chat_id="333333", name="FallbackTarget", chat_type="group")
    source_chat = Chat(telegram_chat_id="444444", name="FallbackSource", chat_type="group")
    db.add(target_chat)
    db.add(source_chat)
    await db.commit()
    
    rule = ForwardRule(
        source_chat_id=source_chat.id,
        target_chat_id=target_chat.id,
        forward_mode=ForwardMode.WHITELIST,
        enable_rule=True
    )
    db.add(rule)
    await db.commit()
    
    # 添加匹配的关键词 ensure fallback forward logic passes
    kw = Keyword(rule_id=rule.id, keyword="fallback", is_blacklist=False)
    db.add(kw)
    await db.commit()
    
    # Reload rule eagerly (similar to other tests)
    stmt = select(ForwardRule).where(ForwardRule.id == rule.id).options(selectinload(ForwardRule.keywords))
    result = await db.execute(stmt)
    rule_loaded = result.scalar_one()

    # 2. 准备各类 Mock
    mock_client = MagicMock()
    mock_client.forward_messages = AsyncMock()
    
    mock_event = MagicMock()
    mock_event.message.text = "This message contains fallback keyword"
    mock_event.chat_id = 444444
    mock_event.message.grouped_id = None
    mock_event.message.id = 999
    
    # 3. Patch factory to Crash
    with patch("handlers.user_handler.get_filter_chain_factory") as mock_factory:
        mock_factory.side_effect = RuntimeError("Simulated Chain Crash")
        
        # 4. Execute
        await process_forward_rule(mock_client, mock_event, 444444, rule_loaded)
        
    # 5. Verify Fallback behavior covers for the crash
    # Fallback logic calls: await client.forward_messages(target_chat_id, event.message, from_peer=event.chat_id)
    mock_client.forward_messages.assert_awaited()
    args = mock_client.forward_messages.await_args
    # Fallback uses POSITIONAL arguments for target_chat_id
    assert args[0][0] == 333333

@pytest.mark.asyncio
async def test_integration_flow_album(db, clear_data):
    """
    测试媒体组(Album)转发:
    验证带有 grouped_id 的消息能被正确透传
    """
    # 1. 准备数据
    target_chat = Chat(telegram_chat_id="555555", name="AlbumTarget", chat_type="group")
    source_chat = Chat(telegram_chat_id="666666", name="AlbumSource", chat_type="group")
    db.add(target_chat)
    db.add(source_chat)
    await db.commit()
    
    rule = ForwardRule(
        source_chat_id=source_chat.id,
        target_chat_id=target_chat.id,
        forward_mode=ForwardMode.BLACKLIST, # 黑名单模式且无关键词 = 转发所有
        enable_rule=True,
        force_pure_forward=True
    )
    db.add(rule)
    await db.commit()
    
    stmt = select(ForwardRule).where(ForwardRule.id == rule.id).options(selectinload(ForwardRule.keywords))
    result = await db.execute(stmt)
    rule_loaded = result.scalar_one()

    # 2. Mock with grouped_id
    mock_client = MagicMock()
    mock_client.forward_messages = AsyncMock()
    
    mock_event = MagicMock()
    mock_event.message.text = "Photo 1 in Album"
    mock_event.chat_id = 666666
    mock_event.message.grouped_id = 123456789
    mock_event.message.id = 1001
    
    # Mock iter_messages for media group logic (it iterates to find siblings)
    async def mock_iter_messages(*args, **kwargs):
        yield mock_event.message
        
    mock_client.iter_messages = MagicMock(side_effect=mock_iter_messages)
    
    # 3. Execute
    await process_forward_rule(mock_client, mock_event, 666666, rule_loaded)
    
    # 4. Verify
    mock_client.forward_messages.assert_awaited()
    # SenderFilter call: await client.forward_messages(entity=..., messages=..., from_peer=...)
    kwargs = mock_client.forward_messages.await_args.kwargs
    # Check target (accepts int or Entity)
    assert str(kwargs.get('entity') or kwargs.get('to_peer')) == "555555"
    # messages passed to forward_messages in pure forward (grouped) is a LIST of IDs
    assert kwargs.get('messages') == [1001]
    assert kwargs.get('from_peer') == 666666
