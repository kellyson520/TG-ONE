"""
Unit tests for SmartDeduplicator logic.
Tests text cleaning, signature generation, and similarity comparison.
"""
import pytest
from unittest.mock import MagicMock
from services.dedup.engine import SmartDeduplicator

class TestSmartDedupLogic:
    
    @pytest.fixture
    def dedup(self):
        d = SmartDeduplicator()
        # Ensure we don't try to load from DB during tests
        d._config_loaded = True
        return d

    def test_clean_text_for_hash(self, dedup):
        """Test text cleaning for hashing/similarity."""
        raw = "Check out this link: https://example.com and follow @user #tag! 123"
        
        # Test default (strip numbers)
        cleaned = dedup._clean_text_for_hash(raw, strip_numbers=True)
        # Should remove URL, @mention, #tag, punctuation, and digits
        assert "check" in cleaned
        assert "out" in cleaned
        assert "this" in cleaned
        assert "link" in cleaned
        assert "follow" in cleaned
        assert "123" not in cleaned
        assert "https" not in cleaned
        assert "@user" not in cleaned
        assert "#tag" not in cleaned
        
        # Test keeping numbers
        cleaned_with_nums = dedup._clean_text_for_hash(raw, strip_numbers=False)
        assert "123" in cleaned_with_nums

    def test_generate_v3_fingerprint_text(self, dedup):
        """Test V3 fingerprint generation for text."""
        msg = MagicMock()
        msg.media = None
        msg.message = "Hello world"
        
        fp = dedup._generate_v3_fingerprint(msg)
        assert fp is not None
        # Type for text is 1
        assert (fp & 0xF) == 1
        # Check if content_bits (SimHash) is present in high 64 bits
        assert (fp >> 64) != 0

    def test_generate_v3_fingerprint_photo(self, dedup):
        """Test V3 fingerprint generation for photos."""
        msg = MagicMock()
        photo = MagicMock()
        photo.access_hash = 123456789
        size = MagicMock()
        size.size = 1024 * 512 # 512 KB
        size.w = 1920
        size.h = 1080
        photo.sizes = [size]
        msg.media = MagicMock(photo=photo)
        
        fp = dedup._generate_v3_fingerprint(msg)
        assert fp is not None
        # Type for photo is 2
        assert (fp & 0xF) == 2
        # Size log for 512KB (bits length of 524288 is 20)
        size_log = (fp >> 4) & 0xFF
        assert size_log == (1024 * 512).bit_length()
        # Stream vector (aspect ratio 1.777 * 1000 = 1777)
        stream_vector = (fp >> 24) & 0xFFFFFFFFFF
        assert stream_vector == 1777

    def test_generate_group_hash(self, dedup):
        """Test record-independent aggregation hash for albums."""
        msg = MagicMock()
        msg.media = MagicMock(photo=MagicMock(access_hash=1, sizes=[]))
        msg.grouped_id = 999
        
        h1 = dedup._generate_content_hash(msg)
        h2 = dedup._generate_content_hash(msg)
        assert h1 == h2
        assert len(h1) == 32 # Hex of 128 bit hash

    def test_is_video_check(self, dedup):
        """Test video detection logic."""
        msg_vid = MagicMock()
        msg_vid.video = MagicMock()
        assert dedup._is_video(msg_vid) is True
        
        msg_doc_vid = MagicMock()
        msg_doc_vid.video = None
        msg_doc_vid.document.mime_type = "video/mp4"
        assert dedup._is_video(msg_doc_vid) is True
        
        msg_text = MagicMock()
        msg_text.video = None
        msg_text.document = None
        assert dedup._is_video(msg_text) is False

    def test_size_bucketing(self, dedup):
        """Test new size log bucketing (log2 scale)."""
        assert dedup._get_size_bucket(0) == 0
        assert dedup._get_size_bucket(1024) == 11 # 2^10 = 1024, bit_length is 11
        assert dedup._get_size_bucket(1024 * 1024) == 21 # bit_length is 21
        
    def test_extract_stream_vector(self, dedup):
        """Test video stream vector extraction."""
        doc = MagicMock()
        doc.w = 1920
        doc.h = 1080
        doc.size = 1234567
        
        vector = dedup._extract_stream_vector(doc)
        assert vector != 0
        assert (vector >> 20) == 1920
        assert ((vector >> 8) & 0xFFF) == 1080
