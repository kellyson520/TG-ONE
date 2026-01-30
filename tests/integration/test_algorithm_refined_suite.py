
import pytest
import asyncio
import os
import shutil
from unittest.mock import MagicMock, AsyncMock, patch

from services.compression_service import CompressionService
from services.bloom_filter import BloomFilter
from services.rate_limiter import RateLimiterPool, RateLimitConfig
from services.metrics_collector import MetricsCollector
from core.algorithms.ac_automaton import ACManager
from services.dedup.engine import SmartDeduplicator
from services.db_buffer import GroupCommitCoordinator
from models.models import MediaSignature

# Setup test data directory
TEST_DATA_DIR = "tests/temp/algo_tests"

@pytest.fixture(autouse=True)
def setup_test_env():
    if not os.path.exists(TEST_DATA_DIR):
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
    yield
    # Cleanup after tests
    if os.path.exists(TEST_DATA_DIR):
        try:
            shutil.rmtree(TEST_DATA_DIR)
        except:
            pass

class TestAlgorithmRefinedSuite:
    """Refined Integration Test Suite for New Algorithmic Modules"""

    @pytest.mark.asyncio
    async def test_compression_pipeline(self):
        """1. Data Compression Pipeline: Verify compression/decompression loop"""
        service = CompressionService(threshold=100) # Small threshold for testing
        
        # Test large text (exceeds threshold)
        large_text = "A" * 200
        compressed, is_compressed = service.compress_if_needed(large_text)
        assert is_compressed is True
        assert isinstance(compressed, bytes)
        assert len(compressed) < len(large_text.encode('utf-8'))
        
        decompressed = service.decompress(compressed)
        assert decompressed == large_text
        
        # Test small text (below threshold)
        small_text = "Short message"
        compressed_small, is_compressed_small = service.compress_if_needed(small_text)
        assert is_compressed_small is False
        assert compressed_small == small_text.encode('utf-8')
        
        # Verify stats
        stats = service.get_stats()
        assert stats["compressed_count"] >= 1
        assert stats["total_original_bytes"] >= 200

    @pytest.mark.asyncio
    async def test_bloom_filter_persistence(self):
        """2. Deduplication Persistence: Verify Bloom Filter state across restarts"""
        bloom_file = os.path.join(TEST_DATA_DIR, "test_bloom.dat")
        if os.path.exists(bloom_file):
            os.remove(bloom_file)
            
        # Instance 1: Add items and save
        bf1 = BloomFilter(capacity=1000, error_rate=0.01, filepath=bloom_file)
        test_item = "unique_msg_123"
        bf1.add(test_item)
        assert test_item in bf1
        bf1.save()
        
        # Instance 2: Load and verify
        bf2 = BloomFilter(capacity=1000, error_rate=0.01, filepath=bloom_file)
        assert test_item in bf2
        assert "non_existent_item" not in bf2

    @pytest.mark.asyncio
    async def test_rate_limiter_and_metrics(self):
        """3. Rate Limiter Pressure Test: Verify throttling and metrics recording"""
        metrics = MetricsCollector()
        # Use a fresh config for the test
        config = RateLimitConfig(rate=5.0, capacity=2, adaptive=False)
        limiter = RateLimiterPool.get_limiter("test_limiter_refined", config)
        limiter.reset_stats()
        
        # Burst: 2 tokens available (capacity)
        assert await limiter.try_acquire() is True
        assert await limiter.try_acquire() is True
        
        # 3rd attempt should be rejected (empty bucket)
        assert await limiter.try_acquire() is False
        
        # Record metrics manually for verification
        metrics.record_rate_limit_stats("test_limiter_refined", limiter.get_stats())
        all_metrics = metrics.get_all_metrics()
        assert "test_limiter_refined" in all_metrics["rate_limit"]
        assert all_metrics["rate_limit"]["test_limiter_refined"]["rejected_requests"] >= 1

    @pytest.mark.asyncio
    async def test_ac_automaton_filtering(self):
        """4. AC Automaton Keyword Filtering: Verify multi-keyword matching"""
        keywords = ["apple", "banana", "cherry", "date"]
        # Use Manager to get automaton
        ac = ACManager.get_automaton(9998, keywords)
        
        text = "I like eating apple and banana for breakfast."
        matches = ac.search(text)
        
        # Indexes of apple (0) and banana (1)
        assert 0 in matches
        assert 1 in matches
        assert 2 not in matches # cherry
        
        assert ac.has_any_match(text) is True
        assert ac.has_any_match("I like durians.") is False

    @pytest.mark.asyncio
    async def test_group_commit_and_dedup_integration(self):
        """5. System Level: Group Commit with Dedup record-back"""
        # Mock DB Session
        mock_session = AsyncMock()
        # Mock session factory context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        
        # Force session.add_all and session.commit to do nothing but be trackable
        mock_session.add_all = MagicMock()
        mock_session.commit = AsyncMock()
        
        mock_factory = MagicMock(return_value=mock_cm)
        
        coordinator = GroupCommitCoordinator(mock_factory)
        coordinator._buffer._batch_size = 2 # Even smaller batch
        coordinator._buffer._flush_interval = 0.05
        await coordinator.start()
        
        # Add signatures to coordinator buffer
        sigs = [
            MediaSignature(chat_id="1", signature="sig1", file_id="f1", content_hash="h1", media_type="photo"),
            MediaSignature(chat_id="1", signature="sig2", file_id="f2", content_hash="h2", media_type="photo"),
        ]
        
        for sig in sigs:
            await coordinator.buffer.add(sig)
            
        # Give enough time for the background task to pick up the items and flush
        # Since _batch_size=2, the 2nd add will call coordinator.trigger_flush()
        # Loop starts with wait_for(event.wait(), timeout=1.0)
        # It should wake up immediately.
        
        await asyncio.sleep(2.0) # Very long wait to be absolutely sure
        
        # Verify db session was used
        assert mock_session.add_all.called, "add_all was not called"
        assert mock_session.commit.called, "commit was not called"
        
        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_smart_dedup_complex_flow(self):
        """6. Smart Dedup: Test content cleaning and similarity"""
        # Create helper to create clean mock messages
        def create_msg(mid, text):
            msg = MagicMock()
            msg.id = mid
            msg.message = text
            # Explicitly set media related attrs to None to avoid auto-mocking as "True"
            msg.photo = None
            msg.video = None
            msg.document = None
            msg.media = None
            msg.grouped_id = None
            return msg

        # Use texts that are different enough to have different content hashes but high similarity
        # Content hash cleaning removes punctuation, but we'll change some words
        t1 = "The quick brown fox jumps over the lazy dog."
        t2 = "The quick brown fox jumps over a lazy cat." 
        
        msg1 = create_msg(1, t1)
        msg2 = create_msg(2, t2)
        
        dedupper = SmartDeduplicator()
        # Disable persistent cache to avoid interference and environmental issues
        dedupper.config["enable_persistent_cache"] = False
        dedupper.config["similarity_threshold"] = 0.6 # Lower threshold for the test
        
        # Mock DB calls
        dedupper.simhash_engine = None
        
        # Force Jaccard similarity for the test to avoid rapidfuzz mock issues
        from services.dedup import engine
        with patch.object(engine, '_HAS_RAPIDFUZZ', False):
            with patch.object(SmartDeduplicator, '_load_config_from_db', return_value=None):
                with patch.object(SmartDeduplicator, '_check_signature_duplicate', return_value=(False, None)):
                    with patch.object(SmartDeduplicator, '_check_content_hash_duplicate', return_value=(False, None)):
                        # 1st message
                        is_dup1, _ = await dedupper.check_duplicate(msg1, target_chat_id=111)
                        assert is_dup1 is False
                        
                        # 2nd message (similar text)
                        is_dup2, reason = await dedupper.check_duplicate(msg2, target_chat_id=111)
                        assert is_dup2 is True, f"Expected duplicate for similar text, got False. Reason: {reason}"
                        assert "相似" in reason or "文本" in reason or "内容" in reason
