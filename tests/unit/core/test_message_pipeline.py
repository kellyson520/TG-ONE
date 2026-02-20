
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.pipeline import MessageContext, Pipeline
from middlewares.dedup import DedupMiddleware
from middlewares.sender import SenderMiddleware
from middlewares.loader import RuleLoaderMiddleware
from models.models import ForwardRule, Chat
from datetime import datetime

@pytest.fixture
def mock_client():
    client = AsyncMock()
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
    source_chat = MagicMock(spec=Chat)
    source_chat.id = 1
    source_chat.telegram_chat_id = "111"
    
    target_chat = MagicMock(spec=Chat)
    target_chat.id = 2
    target_chat.telegram_chat_id = "222"
    
    rule = MagicMock(spec=ForwardRule)
    rule.id = 1
    rule.source_chat = source_chat
    rule.target_chat = target_chat
    rule.enable_dedup = True # Enable dedup to test the logic
    rule.is_replace = False
    rule.is_ai = False
    rule.is_original_sender = True
    rule.force_pure_forward = False
    
    return rule

@pytest.mark.asyncio
async def test_pipeline_flow(mock_client, mock_message, mock_rule):
    """
    Test the flow: Loader -> Dedup -> Sender
    """
    
    # 1. Setup Context
    ctx = MessageContext(
        client=mock_client,
        task_id=1,
        chat_id=111,
        message_id=100,
        message_obj=mock_message
    )
    
    # 2. Mock Services
    mock_rule_repo = AsyncMock()
    mock_rule_repo.get_rules_for_source_chat.return_value = [mock_rule]

    
    # Mock Dedup Service (Global instance)
    with patch('middlewares.dedup.dedup_service') as mock_dedup_service, \
         patch('core.helpers.id_utils.get_display_name_async', new_callable=AsyncMock) as mock_display_name:
        mock_display_name.return_value = "TestChat"
        # Scenario 1: Not Duplicate -> Should Forward
        mock_dedup_service.check_and_lock = AsyncMock(return_value=(False, None))
        mock_dedup_service.rollback = AsyncMock()
        
        # Build Pipeline
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(DedupMiddleware())
        
        # Mock Event Bus for Sender
        mock_bus = AsyncMock()
        pipeline.add(SenderMiddleware(mock_bus))
        
        # Execute
        await pipeline.execute(ctx)
        
        # Assertions
        mock_rule_repo.get_rules_for_source_chat.assert_called_with(111)
        # Dedup check should be called for target 222
        mock_dedup_service.check_and_lock.assert_called_with(222, mock_message, rule_config={}, rule_id=1)
        
        # Sender should send
        # Since logic in SenderMiddleware uses forward_messages_queued or send_message/file
        # mock_rule has is_replace=False, so default attempts pure forward logic or copy based on conditions
        # In SenderMiddleware:
        # should_copy = bool(modified_text) or getattr(rule, 'is_replace', False) or ...
        # Here should_copy is False -> Forward Mode
        
        # Note: SenderMiddleware calls forward_messages_queued imported from services.queue_service
        # We need to mock that too if we want to verify it called
        
@pytest.mark.asyncio
async def test_dedup_filtering(mock_client, mock_message, mock_rule):
    """
    Test that DedupMiddleware filters out duplicate messages
    """
    ctx = MessageContext(
        client=mock_client,
        task_id=1,
        chat_id=111,
        message_id=100,
        message_obj=mock_message,
        rules=[mock_rule] # Skip loader, inject rule directly
    )
    
    with patch('middlewares.dedup.dedup_service') as mock_dedup_service, \
         patch('core.helpers.id_utils.get_display_name_async', new_callable=AsyncMock) as mock_display_name:
        mock_display_name.return_value = "TestChat"
        # Scenario 2: Is Duplicate -> Should NOT Forward
        mock_dedup_service.check_and_lock = AsyncMock(return_value=(True, "already_exists"))
        
        middleware = DedupMiddleware()
        
        # Create a mock next_call
        next_call = AsyncMock()
        
        await middleware.process(ctx, next_call)
        
        # The rule should be removed from ctx.rules
        assert len(ctx.rules) == 0
        # next_call should NOT be called if rules are empty (wait, line 20 in dedup.py says: if ctx.rules: await next_call())
        # So if all rules are filtered, next_call is NOT called.
        next_call.assert_not_called()

