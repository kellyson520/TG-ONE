import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.dedup.engine import SmartDeduplicator
import time

@pytest.fixture
def dedup():
    dedup = SmartDeduplicator()
    
    # Mock repositories (AsyncMock for async methods)
    dedup._repo = MagicMock()
    dedup._repo.exists_media_signature = AsyncMock(return_value=False) # Default
    dedup._repo.check_content_hash_duplicate = AsyncMock(return_value=(False, ""))
    
    dedup._pcache_repo = MagicMock()
    dedup._pcache_repo.get = AsyncMock(return_value=None) # Default miss
    
    # Disable components
    dedup.bloom_filter = None 
    dedup.hll = None
    
    # Ensure caches are empty
    dedup.time_window_cache = {}
    dedup.content_hash_cache = {}
    
    return dedup

@pytest.mark.asyncio
async def test_smart_dedup_skips_media_sig(dedup):
    message = MagicMock()
    # 模拟一个带图片的原始消息
    message.photo = MagicMock()
    message.photo.sizes = [SimpleNamespace(w=100, h=100, size=1000)]
    message.message = "unique text"
    
    chat_id = 12345
    config = {'enable_content_hash': True}
    
    # First, normal check (no skip)
    # We patch the tools function used by SignatureStrategy
    with patch("services.dedup.tools.generate_signature", return_value="photo:100x100:1000") as mock_sig:
        # Mock repo to return True for signature existence
        dedup.repo.exists_media_signature = AsyncMock(return_value=True)
        dedup.time_window_cache = {} # Ensure cache miss first to hit repo
        
        is_dup, reason = await dedup.check_duplicate(message, chat_id, config)
        print(f"DEBUG TEST: is_dup={is_dup}, reason={reason}")
        assert is_dup is True
        assert "数据库中存在" in reason or "重复" in reason
        mock_sig.assert_called()

    # Then, enable skip_media_sig check
    with patch("services.dedup.tools.generate_signature", return_value="photo:100x100:1000") as mock_sig:
         # Mock content hash check to return False (so we don't duplicate on content)
         dedup.repo.check_content_hash_duplicate = AsyncMock(return_value=(False, ""))
         
         # Construct config dict with content hash disabled to isolate signature check
         test_config_isolated = config.copy()
         test_config_isolated['enable_content_hash'] = False
         test_config_isolated['enable_video_file_id_check'] = False
         
         # Note: skip_media_sig=True is passed as kwarg to check_duplicate
         is_dup, reason = await dedup.check_duplicate(message, chat_id, test_config_isolated, skip_media_sig=True)
         
         # With skip_media_sig=True, SignatureStrategy returns None immediately
         # So mock_sig (generate_signature) should NOT be called by SignatureStrategy
         # However, ContentStrategy *might* call generate_content_hash which *might* call generate_signature inside tools...
         # But SignatureStrategy specifically should return None early.
         
         # Verify we didn't hit signature dup logic
         assert "signature" not in reason 
         if not is_dup:
             assert True
         else:
             # If it is dup, ensure it's not signature
             assert "signature" not in reason

         # Wait, looking at current implementation:
         # SignatureStrategy: if config.skip_media_sig: return None.
         # So generate_signature is NOT called by SignatureStrategy.
         # But let's check tools usage.
         
         mock_sig.assert_not_called()

from types import SimpleNamespace
