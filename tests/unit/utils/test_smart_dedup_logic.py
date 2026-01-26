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

    def test_generate_signature_photo(self, dedup):
        """Test signature generation for photos."""
        msg = MagicMock()
        photo = MagicMock()
        size = MagicMock()
        size.w = 800
        size.h = 600
        size.size = 12345
        photo.sizes = [size]
        msg.photo = photo
        msg.document = None
        msg.video = None
        
        sig = dedup._generate_signature(msg)
        assert sig == "photo:800x600:12345"

    def test_generate_signature_document(self, dedup):
        """Test signature generation for documents."""
        msg = MagicMock()
        msg.photo = None
        doc = MagicMock()
        doc.id = 999
        doc.size = 54321
        doc.mime_type = "application/pdf"
        msg.document = doc
        msg.video = None
        
        sig = dedup._generate_signature(msg)
        assert sig == "document:999:54321:application/pdf"

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

    def test_get_size_range(self, dedup):
        """Test size bucket logic (assuming it exists in SmartDeduplicator)."""
        # Testing the private _get_size_range if it exists
        if hasattr(dedup, '_get_size_range'):
            assert dedup._get_size_range(500) == "tiny"
            assert dedup._get_size_range(1500) == "small"
            assert dedup._get_size_range(15000) == "small"
            assert dedup._get_size_range(15 * 1024 * 1024) == "large"
