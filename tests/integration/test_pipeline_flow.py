
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.pipeline import Pipeline, MessageContext
from middlewares.loader import RuleLoaderMiddleware
from middlewares.dedup import DedupMiddleware
from middlewares.filter import FilterMiddleware
from models.models import ForwardRule, Chat
from types import SimpleNamespace

# ==============================================================================
# Helper Factories
# ==============================================================================

def create_mock_message(id=1, text="Hello", chat_id=123, grouped_id=None):
    msg = MagicMock()
    msg.id = id
    msg.text = text
    msg.message = text # Telethon alias
    msg.chat_id = chat_id
    msg.grouped_id = grouped_id
    msg.media = None
    msg.date = None
    return msg

def create_mock_rule(id=1, source_id=123, target_id=456, enable_dedup=False):
    rule = ForwardRule()
    rule.id = id
    rule.name = "TestRule"
    rule.source_chat_id = source_id
    rule.target_chat_id = target_id
    rule.enable_rule = True
    rule.enable_dedup = enable_dedup # Default off for basic tests
    rule.is_ai = False
    
    # Mocks for relationships
    rule.source_chat = Chat(id=source_id, telegram_chat_id=str(source_id), name="Source")
    rule.target_chat = Chat(id=target_id, telegram_chat_id=str(target_id), name="Target")
    
    # Initialize list relationships
    rule.keywords = []
    rule.replace_rules = []
    rule.media_extensions = []
    rule.media_types = None # Or object with all False
    rule.rss_config = None
    rule.push_config = None
    rule.rule_syncs = []
    
    # Enum mocks
    from enums.enums import MessageMode, PreviewMode
    rule.message_mode = MessageMode.MARKDOWN
    rule.is_preview = PreviewMode.ON
    
    return rule

# ==============================================================================
# Test Fixtures And Setup
# ==============================================================================

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.send_message = AsyncMock(return_value=MagicMock(id=999))
    client.send_file = AsyncMock(return_value=MagicMock(id=999))
    return client

@pytest.fixture
def mock_rule_repo():
    repo = AsyncMock()
    return repo

@pytest.fixture
def pipeline_env(mock_client, mock_rule_repo):
    """Setup a pipeline environment with mocked dependencies"""
    
    # 1. Pipeline
    pipeline = Pipeline()
    
    # 2. Middlewares
    # Loader
    loader = RuleLoaderMiddleware(mock_rule_repo)
    
    # Dedup (Patching the global service import)
    dedup = DedupMiddleware()
    
    # Filter
    filter_mw = FilterMiddleware()
    
    # Mock complex filters to avoid environment dependency issues during integration
    # We focus on the pipeline mechanism: Loader -> Dedup -> Filter Chain -> Sender
    
    mock_global = MagicMock()
    mock_global._process = AsyncMock(return_value=True)
    filter_mw.global_filter = mock_global
    
    mock_adv = MagicMock()
    mock_adv._process = AsyncMock(return_value=True)
    filter_mw.advanced_media_filter = mock_adv
    
    mock_media = MagicMock()
    mock_media._process = AsyncMock(return_value=True)
    filter_mw.media_filter = mock_media
    
    mock_init = MagicMock()
    mock_init._process = AsyncMock(return_value=True)
    filter_mw.init_filter = mock_init
    
    mock_kw = MagicMock()
    async def set_should_forward(ctx):
         ctx.should_forward = True
         return True
    mock_kw._process = AsyncMock(side_effect=set_should_forward)
    filter_mw.keyword_filter = mock_kw
    
    # Add to pipeline
    pipeline.add(loader)
    pipeline.add(dedup)
    pipeline.add(filter_mw)
    
    return pipeline, loader, dedup, filter_mw

# ==============================================================================
# Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_pipeline_basic_flow(pipeline_env, mock_rule_repo, mock_client):
    """
    Test Case 1: Standard Success Flow
    """
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    pipeline, _, _, filter_mw = pipeline_env
    
    # Setup Data
    msg = create_mock_message(id=100, text="Test Message")
    rule = create_mock_rule(enable_dedup=False)
    
    # Mock Repo to return rule
    mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
    
    # Mock Dedup Service, DBOperations, and SenderFilter util
    with patch('middlewares.dedup.dedup_service') as mock_dedup_svc, \
         patch('utils.db.db_operations.DBOperations') as mock_db_ops_cls, \
         patch('utils.helpers.id_utils.resolve_entity_by_id_variants', new_callable=AsyncMock) as mock_resolve:
        
        mock_dedup_svc.is_duplicate = AsyncMock(return_value=False)
        mock_db_ops = AsyncMock()
        mock_db_ops_cls.create = AsyncMock(return_value=mock_db_ops)
        mock_db_ops_cls.get_instance = AsyncMock(return_value=mock_db_ops)
        
        # Mock resolve return value
        mock_resolve.return_value = (MagicMock(), 456)
        
        # Create Context
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=123,
            message_id=100,
            message_obj=msg,
            is_group=False
        )
        
        # Execute
        await pipeline.execute(ctx)
        
        # Assertions
        assert ctx.is_terminated is False
        assert len(ctx.rules) == 1
        
        assert mock_client.send_message.call_count >= 1
        args, _ = mock_client.send_message.call_args
        assert args[0] == 456 # Target ID
        assert "Test Message" in args[1]


@pytest.mark.asyncio
async def test_pipeline_dedup_block(pipeline_env, mock_rule_repo, mock_client):
    """
    Test Case 2: Dedup Block
    """
    pipeline, _, _, _ = pipeline_env
    
    msg = create_mock_message(id=101)
    rule = create_mock_rule(id=2, enable_dedup=True)
    
    mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
    
    with patch('middlewares.dedup.dedup_service') as mock_dedup_svc:
        # Simulate Duplicate
        mock_dedup_svc.check_and_record = AsyncMock(return_value=(True, "Simulated Dup"))
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=123,
            message_id=101,
            message_obj=msg
        )
        
        await pipeline.execute(ctx)
        
        # Assert blocked
        # DedupMiddleware sets ctx.rules to empty if all are blocked
        assert len(ctx.rules) == 0
        # Pipeline terminates if no rules
        # But Wait, DedupMiddleware calls next_call ONLY if rules exist
        # If no rules, it does NOT call next_call, effectively terminating specific branch
        
        # Check client NOT called
        mock_client.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_pipeline_attribute_fix_verification(pipeline_env, mock_rule_repo, mock_client):
    """
    Test Case 3: Verify 'original_message_text' exists in context
    (Regresson Test for the Attribute Error)
    """
    pipeline, _, _, filter_mw = pipeline_env
    
    msg = create_mock_message(text="Original Text")
    rule = create_mock_rule()
    rule.is_ai = True # Enable AI to force AI Filter execution (which uses the attribute)
    
    mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
    
    # Mock AI Filter to avoid actual API calls, but verify Context
    with patch('middlewares.dedup.dedup_service'), \
         patch.object(filter_mw.ai_filter, '_process', side_effect=AsyncMock(return_value=True)) as mock_ai_process:
        
        ctx = MessageContext(
            client=mock_client,
            task_id=1,
            chat_id=123,
            message_id=102,
            message_obj=msg
        )
        
        await pipeline.execute(ctx)
        
        # Verify call args of ai_filter._process(filter_ctx)
        call_args = mock_ai_process.call_args
        filter_ctx = call_args[0][0]
        
        # CRITICAL ASSERTIONS
        assert hasattr(filter_ctx, 'original_message_text')
        assert filter_ctx.original_message_text == "Original Text"
        assert hasattr(filter_ctx, 'is_media_group')
        assert filter_ctx.is_media_group is False

@pytest.mark.asyncio
async def test_pipeline_no_rules_flow(pipeline_env, mock_rule_repo, mock_client):
    """
    Test Case 4: No Rules Found
    """
    pipeline, _, _, _ = pipeline_env
    
    mock_rule_repo.get_rules_for_source_chat.return_value = []
    
    ctx = MessageContext(
        client=mock_client,
        task_id=1,
        chat_id=999,
        message_id=1,
        message_obj=create_mock_message()
    )
    
    await pipeline.execute(ctx)
    
    assert ctx.is_terminated is True
    # Client should not be called
    mock_client.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_pipeline_dedup_rollback(pipeline_env, mock_rule_repo, mock_client):
    """
    Test Case 5: Dedup Rollback on Failure
    """
    pipeline, _, _, filter_mw = pipeline_env
    
    # Setup Data
    msg = create_mock_message(id=200, text="Rollback Test")
    rule = create_mock_rule(enable_dedup=True)
    
    # Mock Repo
    mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
    
    # Mock Dedup Service and DBOperations
    with patch('middlewares.dedup.dedup_service') as mock_dedup_svc, \
         patch('utils.db.db_operations.DBOperations') as mock_db_ops_cls, \
         patch('utils.helpers.id_utils.resolve_entity_by_id_variants', new_callable=AsyncMock) as mock_resolve:
        
        # Mock Check Logic: First time NOT duplicate
        mock_dedup_svc.check_and_record = AsyncMock(return_value=(False, "Mock"))
        mock_dedup_svc.rollback = AsyncMock()
        
        mock_db_ops = AsyncMock()
        mock_db_ops_cls.create = AsyncMock(return_value=mock_db_ops)
        mock_db_ops_cls.get_instance = AsyncMock(return_value=mock_db_ops)
        
        mock_resolve.return_value = (MagicMock(), 456)

        # Mock Client Failure
        mock_client.send_message.side_effect = Exception("Network Error")
        
        # Initialize filters
        mock_init = MagicMock()
        mock_init._process = AsyncMock(return_value=True)
        filter_mw.init_filter = mock_init
        
        mock_kw = MagicMock()
        async def set_should_forward(ctx):
             ctx.should_forward = True
             return True
        mock_kw._process = AsyncMock(side_effect=set_should_forward)
        filter_mw.keyword_filter = mock_kw
        


        # Create Context
        ctx = MessageContext(
            client=mock_client,
            task_id=2,
            chat_id=123,
            message_id=200,
            message_obj=msg
        )
        # Ensure context has failed_rules (init logic handles this, but here it's new context)
        # MessageContext defined in core/pipeline.py now has failed_rules default factory.
        
        # Execute
        await pipeline.execute(ctx)
        
        # Debug
        # Assertions
        # 1. Pipeline SHOULD be terminated because SenderFilter failed for the only rule
        assert ctx.is_terminated is True
        
        # 2. failed_rules should contain rule.id
        assert rule.id in ctx.failed_rules
        
        # 3. Rollback MUST be called
        mock_dedup_svc.rollback.assert_called_once()
        args, _ = mock_dedup_svc.rollback.call_args
        # Args: target_chat_id, message_obj
        assert args[0] == 456
        assert args[1] == msg
