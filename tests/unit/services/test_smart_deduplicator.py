import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.dedup.engine import SmartDeduplicator, DedupConfig
from services.dedup.types import DedupResult
from services.dedup import tools

@pytest.fixture
def dedup():
    dedup = SmartDeduplicator()
    
    # Mock repositories (AsyncMock for async methods)
    dedup._repo = MagicMock()
    dedup._repo.exists_media_signature = AsyncMock(return_value=False)
    dedup._repo.check_content_hash_duplicate = AsyncMock(return_value=(False, ""))
    dedup._repo.exists_video_file_id = AsyncMock(return_value=False)
    dedup._repo.add_media_signature = AsyncMock()
    dedup._repo.add_content_hash = AsyncMock()
    dedup._repo.add_text_fingerprint = AsyncMock()
    dedup._repo.save_config = AsyncMock()
    dedup._repo.add_or_update = AsyncMock()
    
    dedup._pcache_repo = MagicMock()
    dedup._pcache_repo.get = AsyncMock(return_value=None)
    dedup._pcache_repo.set = AsyncMock()
    
    # Disable components
    dedup.bloom_filter = None 
    dedup.hll = None
    
    # Ensure caches are empty
    dedup.time_window_cache = {}
    dedup.content_hash_cache = {}
    dedup.text_fp_cache = {}
    
    return dedup

@pytest.fixture
def msg():
    """Create a basic message mock"""
    m = MagicMock()
    m.id = 100
    m.message = "Hello World"
    # Set default media to None
    m.photo = None
    m.video = None
    m.document = None
    m.media = None
    m.grouped_id = None
    return m

@pytest.mark.asyncio
async def test_check_duplicate_signature_hit(dedup, msg):
    """Test signature duplicate detection from repo"""
    chat_id = 12345
    config = {'enable_dedup': True}
    
    # Setup mock to return True for signature
    dedup.repo.exists_media_signature.return_value = True
    
    with patch("services.dedup.tools.generate_signature", return_value="sig:123"):
        is_dup, reason = await dedup.check_duplicate(msg, chat_id, config)
        
        assert is_dup is True
        assert "数据库" in reason
        dedup.repo.exists_media_signature.assert_called_once()

@pytest.mark.asyncio
async def test_check_duplicate_content_hash_hit(dedup, msg):
    """Test content hash duplicate detection from repo"""
    chat_id = 12345
    config = {'enable_dedup': True, 'enable_content_hash': True}
    
    # Signature returns None or False
    dedup.repo.exists_media_signature.return_value = False
    
    # Content hash returns True
    dedup.repo.check_content_hash_duplicate.return_value = (True, "content dup")
    
    with patch("services.dedup.tools.generate_signature", return_value=None):
        with patch("services.dedup.tools.generate_content_hash", return_value="hash:123"):
            is_dup, reason = await dedup.check_duplicate(msg, chat_id, config)
            
            assert is_dup is True
            assert "content dup" in reason
            dedup.repo.check_content_hash_duplicate.assert_called_once()

@pytest.mark.asyncio
async def test_check_duplicate_video_file_id_hit(dedup, msg):
    """Test video file_id duplicate detection"""
    chat_id = 12345
    config = {'enable_dedup': True, 'enable_video_file_id_check': True}
    
    # Make message a video
    msg.video = MagicMock()
    msg.video.id = 999
    
    # Config mocks
    dedup.repo.exists_video_file_id.return_value = True
    
    with patch("services.dedup.tools.is_video", return_value=True):
        with patch("services.dedup.tools.extract_video_file_id", return_value=999):
            is_dup, reason = await dedup.check_duplicate(msg, chat_id, config)
            
            assert is_dup is True
            assert "FileID" in reason
            dedup.repo.exists_video_file_id.assert_called_once()

@pytest.mark.asyncio
async def test_no_duplicate_records_message(dedup, msg):
    """Test that non-duplicate message triggers recording"""
    chat_id = 12345
    config = {'enable_dedup': True}
    
    # Ensure all checks return False (default in fixture)
    
    with patch("services.dedup.tools.generate_signature", return_value="sig:new"):
        with patch("services.dedup.tools.generate_content_hash", return_value="hash:new"):
            is_dup, reason = await dedup.check_duplicate(msg, chat_id, config)
            
            assert is_dup is False
            assert "无重复" in reason
            
            # Verify recording (Buffered)
            assert len(dedup._write_buffer) == 1
            payload = dedup._write_buffer[0]
            assert payload['signature'] == "sig:new"
            assert payload['content_hash'] == "hash:new"
            
            # Verify memory cache updated
            assert str(chat_id) in dedup.time_window_cache
            assert "sig:new" in dedup.time_window_cache[str(chat_id)]

@pytest.mark.asyncio
async def test_readonly_mode(dedup, msg):
    """Test readonly mode does NOT record message"""
    chat_id = 12345
    config = {'enable_dedup': True}
    
    with patch("services.dedup.tools.generate_signature", return_value="sig:ro"):
        is_dup, reason = await dedup.check_duplicate(msg, chat_id, config, readonly=True)
        
        assert is_dup is False
        
        # Verify recording NOT called
        assert len(dedup._write_buffer) == 0
        
        # Verify memory cache NOT updated
        assert str(chat_id) not in dedup.time_window_cache
