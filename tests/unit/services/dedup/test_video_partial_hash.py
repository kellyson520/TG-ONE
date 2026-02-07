
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.dedup.engine import SmartDeduplicator, DedupConfig
from services.dedup.types import DedupResult
from services.dedup import tools

@pytest.fixture
def dedup():
    dedup = SmartDeduplicator()
    # Mock repo correctly with AsyncMocks for awaitable methods
    dedup._repo = MagicMock()
    dedup._repo.exists_media_signature = AsyncMock(return_value=False)
    dedup._repo.exists_video_file_id = AsyncMock(return_value=False)
    dedup._repo.check_content_hash_duplicate = AsyncMock(return_value=(False, ""))
    dedup._repo.add_media_signature = AsyncMock()
    dedup._repo.add_content_hash = AsyncMock()
    dedup._repo.add_text_fingerprint = AsyncMock()
    
    # Disable others
    dedup.bloom_filter = None 
    dedup.hll = None
    dedup.time_window_cache = {}
    
    return dedup

@pytest.mark.asyncio
async def test_video_partial_hash_check(dedup):
    """Test verification of video partial hash"""
    chat_id = 12345
    config = {'enable_dedup': True, 'enable_video_partial_hash_check': True}
    
    msg = MagicMock()
    msg.file_path = "video_file.mp4"
    msg.video = MagicMock() # Ensure is_video returns True
    
    # Setup repo to return True for partial hash signature
    # expected signature: video_partial:<hash>
    dedup.repo.exists_media_signature.side_effect = lambda cid, sig: sig == "video_partial:mockhash123"
    
    with patch("services.dedup.strategies.video.os.path.exists", return_value=True):
        with patch("services.dedup.strategies.video.calculate_video_partial_file_hash", return_value="mockhash123"):
            is_dup, reason = await dedup.check_duplicate(msg, chat_id, config)
            
            assert is_dup is True
            assert "PartialHash" in reason
            assert "video_partial:mockhash123" in dedup.repo.exists_media_signature.call_args[0][1]

@pytest.mark.asyncio
async def test_video_partial_hash_skip_if_no_file(dedup):
    """Test skip check if file path missing"""
    chat_id = 12345
    config = {'enable_dedup': True, 'enable_video_partial_hash_check': True}
    
    msg = MagicMock()
    msg.file_path = None
    msg.file = None
    
    # Repo always False
    dedup.repo.exists_media_signature.return_value = False
    
    with patch("services.dedup.tools.calculate_video_partial_file_hash") as mock_calc:
        is_dup, reason = await dedup.check_duplicate(msg, chat_id, config)
        
        assert is_dup is False
        mock_calc.assert_not_called()

@pytest.mark.asyncio
async def test_simhash_calculation():
    """Test SimHash calculation actually calls compute_simhash"""
    from services.dedup.tools import calculate_simhash
    
    with patch("services.dedup.tools.compute_simhash", return_value=123456789) as mock_compute:
        res = calculate_simhash("hello world")
        assert res == 123456789
        mock_compute.assert_called_with("hello world")
