"""
Integration Test: Mixed Media Flow (80 items, 8 types)
Tests the complete pipeline: Listen -> Handler -> Filter -> Dedup -> Sender with random media types.
"""
import pytest
import random
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from core.pipeline import MessageContext, Pipeline
from middlewares.loader import RuleLoaderMiddleware
from middlewares.filter import FilterMiddleware
from middlewares.dedup import DedupMiddleware
from middlewares.sender import SenderMiddleware
from models.models import ForwardRule, Chat

# Mock Telethon Types
class DocumentAttribute:
    pass

class DocumentAttributeValid(DocumentAttribute):
    def __init__(self):
        pass

class DocumentAttributeFilename(DocumentAttribute):
    def __init__(self, file_name):
        self.file_name = file_name

class DocumentAttributeAudio(DocumentAttribute):
    def __init__(self, voice=False, title="", performer=""):
        self.voice = voice
        self.title = title
        self.performer = performer

class DocumentAttributeVideo(DocumentAttribute):
    def __init__(self, duration=0, w=0, h=0):
        self.duration = duration
        self.w = w
        self.h = h

class DocumentAttributeSticker(DocumentAttribute):
    def __init__(self, alt="", stickerset=None):
        self.alt = alt
        self.stickerset = stickerset

class MessageEntityUrl:
    def __init__(self, offset, length):
        self.offset = offset
        self.length = length

class TestMixedMediaIntegration:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.session = AsyncMock()
        return db
    
    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.send_message = AsyncMock()
        client.send_file = AsyncMock()
        client.forward_messages = AsyncMock()
        client.delete_messages = AsyncMock()
        return client

    @pytest.fixture
    def create_rule(self):
        def _create(rule_id=1, keywords=None):
            source_chat = MagicMock(spec=Chat)
            source_chat.id = 1
            source_chat.telegram_chat_id = "1001"
            
            target_chat = MagicMock(spec=Chat)
            target_chat.id = 2
            target_chat.telegram_chat_id = "2002"
            
            rule = MagicMock(spec=ForwardRule)
            rule.id = rule_id
            rule.source_chat = source_chat
            rule.target_chat = target_chat
            rule.enable_dedup = False # Disable dedup for this specific flow test unless explicitly testing duplicates
            rule.is_replace = False
            rule.is_ai = False
            rule.is_original_sender = False
            rule.force_pure_forward = False
            rule.keywords = keywords or [] # If keywords present, filter logic should use them
            # For simplicity, let's assume 'FilterMiddleware' uses `filters/keyword_filter.py` logic which reads `rule.keywords`
            
            # Setup Rule attributes expected by Middleware
            rule.replace_rules = []
            
            return rule
        return _create

    def create_mock_message(self, msg_id, type_name, should_filter=False):
        """Factory for 8 types of media messages"""
        msg = MagicMock()
        msg.id = msg_id
        msg.date = datetime.now()
        msg.grouped_id = None
        msg.sender_id = 999
        msg.chat_id = 1001
        msg.out = False
        
        # Determine content based on should_filter
        trigger_word = "BLOCKME" if should_filter else "SAFE"
        msg.text = f"Message {msg_id} ({type_name}) - {trigger_word}"
        
        msg.media = None
        msg.document = None
        msg.photo = None
        msg.entities = []

        if type_name == "text":
            # Just text
            pass
            
        elif type_name == "image":
            msg.media = MagicMock()
            msg.media.photo = MagicMock()
            msg.photo = msg.media.photo
            msg.text = "" # Captions are optional for images
            if should_filter:
                msg.text = f"Image caption {trigger_word}"

        elif type_name == "video":
            msg.media = MagicMock()
            msg.media.document = MagicMock()
            msg.document = msg.media.document
            msg.document.mime_type = "video/mp4"
            msg.document.attributes = [DocumentAttributeVideo(10, 1920, 1080)]
            msg.text = ""
            if should_filter: msg.text = f"Video caption {trigger_word}"

        elif type_name == "voice":
            msg.media = MagicMock()
            msg.media.document = MagicMock()
            msg.document = msg.media.document
            msg.document.mime_type = "audio/ogg"
            msg.document.attributes = [DocumentAttributeAudio(voice=True, title="Voice Note")]
            msg.text = "" 
            if should_filter: msg.text = f"Voice caption {trigger_word}"

        elif type_name == "audio":
            msg.media = MagicMock()
            msg.media.document = MagicMock()
            msg.document = msg.media.document
            msg.document.mime_type = "audio/mpeg"
            msg.document.attributes = [DocumentAttributeAudio(voice=False, title="Song", performer="Artist")]
            msg.text = ""
            if should_filter: msg.text = f"Audio caption {trigger_word}"

        elif type_name == "file":
            msg.media = MagicMock()
            msg.media.document = MagicMock()
            msg.document = msg.media.document
            msg.document.mime_type = "application/pdf"
            msg.document.attributes = [DocumentAttributeFilename("document.pdf")]
            msg.text = ""
            if should_filter: msg.text = f"File caption {trigger_word}"

        elif type_name == "sticker":
            msg.media = MagicMock()
            msg.media.document = MagicMock()
            msg.document = msg.media.document
            msg.document.mime_type = "image/webp" # Typical sticker mime
            msg.document.attributes = [DocumentAttributeSticker(alt="👋")]
            msg.text = "" 
            if should_filter: msg.text = f"Sticker caption {trigger_word}"

        elif type_name == "link":
             msg.text = f"Check this out: https://example.com/foo {trigger_word}"
             msg.entities = [MessageEntityUrl(offset=16, length=23)]

        return msg

    @pytest.mark.asyncio
    async def test_mixed_media_flow_simulation(self, mock_client, create_rule):
        """
        Main Test: Simulate 80 mixed messages flowing through the system.
        Verifies Listen -> Filter -> Forward integration.
        """
        print("\n=== Starting Mixed Media Integration Test (80 items) ===")
        
        # 1. Generate Data
        types = ["text", "image", "video", "voice", "audio", "file", "sticker", "link"]
        messages = []
        msg_id_counter = 1000
        
        expected_pass_count = 0
        expected_filter_count = 0
        
        for t in types:
            for i in range(10):
                # Mark 2 out of 10 as "should filter" to test boundary
                should_filter = (i >= 8) 
                msg = self.create_mock_message(msg_id_counter, t, should_filter)
                messages.append({
                    'msg': msg,
                    'type': t,
                    'should_filter': should_filter
                })
                msg_id_counter += 1
                
                if should_filter:
                    expected_filter_count += 1
                else:
                    expected_pass_count += 1
        
        # 2. Randomize Order
        random.shuffle(messages)
        print(f"Generated {len(messages)} messages. Expected Pass: {expected_pass_count}, Expected Filter: {expected_filter_count}")

        # 3. Setup Pipeline Components
        rule = create_rule(rule_id=1, keywords=["BLOCKME"])
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        # Add Filter Middleware - assume it uses standard factory which respects `keywords`
        # We need to ensure 'filters.factory' is working or mocked to respect 'keywords'
        
        # IMPORTANT: Mocking the filter factory to ensure deterministic behavior for this test
        # Instead of relying on complex real filter chains, we mock the factory to return a chain 
        # that checks for "BLOCKME" in text/caption.
        with patch('middlewares.filter.get_filter_chain_factory') as mock_factory_getter:
            mock_chain = AsyncMock()
            
            async def mock_process_context(ctx):
                # Simple Logic: Check text for "BLOCKME"
                text = ctx.message_text or ''
                
                if "BLOCKME" in text:
                    return False # Blocked
                return True # Passed
            
            mock_chain.process_context.side_effect = mock_process_context
            mock_factory = MagicMock()
            mock_factory.create_chain_for_rule.return_value = mock_chain
            mock_factory_getter.return_value = mock_factory
            
            pipeline.add(FilterMiddleware())
            
            # Dedup Middleware (Mocked to always pass new items)
            pipeline.add(DedupMiddleware())
            
            # Sender Middleware
            pipeline.add(SenderMiddleware(mock_bus))

            # 4. Run Simulation
            actual_pass_count = 0
            actual_filter_count = 0
            
            # Mock Dedup Service inside DedupMiddleware
            with patch('middlewares.dedup.dedup_service') as mock_dedup:
                mock_dedup.check_and_lock = AsyncMock(return_value=(False, None))
                
                # Mock Sender Queue inside SenderMiddleware
                with patch('middlewares.sender.forward_messages_queued') as mock_forward:
                    mock_forward.return_value = AsyncMock()
                    
                    # Also mock UnifiedSender for Copy mode (if triggered)
                    with patch('core.helpers.smart_retry.retry_manager') as mock_retry:
                        mock_retry.execute = AsyncMock()

                        for item in messages:
                            msg_obj = item['msg']
                            ctx = MessageContext(
                                client=mock_client,
                                task_id=1,
                                chat_id=1001,
                                message_id=msg_obj.id,
                                message_obj=msg_obj
                            )
                            
                            # Execute Pipeline
                            await pipeline.execute(ctx)
                            
                            if ctx.is_terminated or not ctx.rules:
                                actual_filter_count += 1
                                # Verify it was indeed supposed to be filtered
                                if not item['should_filter']:
                                    print(f"❌ Unexpected Filter: {item['type']} ID={msg_obj.id} Text='{msg_obj.text}'")
                            else:
                                actual_pass_count += 1
                                # Verify it was indeed supposed to pass
                                if item['should_filter']:
                                    print(f"❌ Unexpected Pass: {item['type']} ID={msg_obj.id} Text='{msg_obj.text}'")

        # 5. Assertions
        print(f"\nResults: Pass={actual_pass_count}/{expected_pass_count}, Filter={actual_filter_count}/{expected_filter_count}")
        
        if actual_pass_count != expected_pass_count or actual_filter_count != expected_filter_count:
             assert False, f"MISMATCH: Pass={actual_pass_count}/{expected_pass_count}, Filter={actual_filter_count}/{expected_filter_count}"
        
        # Verify Sender calls
        # Since we mocked retry_manager.execute, we check call count there
        # For pure forward: mock_retry.execute called with forward_messages_queued
        # For copy: mock_retry.execute called with sender.send
        assert mock_retry.execute.call_count == expected_pass_count, \
            f"Sender execution count {mock_retry.execute.call_count} != Expected Pass {expected_pass_count}"

        print("✅ Integration Test Passed Successfully!")
