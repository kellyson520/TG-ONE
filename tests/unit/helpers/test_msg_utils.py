"""msg_utils 测试 — detect_message_type 消息类型检测"""
import pytest
from unittest.mock import MagicMock
from core.helpers.msg_utils import detect_message_type


def _make_message(**attrs):
    """创建 mock 消息对象"""
    msg = MagicMock(spec=[])
    for k, v in attrs.items():
        setattr(msg, k, v)
    return msg


class TestDetectMessageType:
    """消息类型检测测试"""

    def test_none_returns_unknown(self):
        assert detect_message_type(None) == "unknown"

    def test_photo(self):
        msg = _make_message(photo=True)
        assert detect_message_type(msg) == "photo"

    def test_video(self):
        msg = _make_message(video=True)
        assert detect_message_type(msg) == "video"

    def test_gif(self):
        msg = _make_message(document=True, gif=True)
        assert detect_message_type(msg) == "gif"

    def test_voice(self):
        msg = _make_message(document=True, voice=True)
        assert detect_message_type(msg) == "voice"

    def test_audio(self):
        msg = _make_message(document=True, audio=True)
        assert detect_message_type(msg) == "audio"

    def test_sticker(self):
        msg = _make_message(document=True, sticker=True)
        assert detect_message_type(msg) == "sticker"

    def test_video_note(self):
        msg = _make_message(document=True, video_note=True)
        assert detect_message_type(msg) == "video_note"

    def test_document_generic(self):
        """document 但没有细分类型"""
        msg = _make_message(document=True)
        assert detect_message_type(msg) == "document"

    def test_contact(self):
        msg = _make_message(contact=True)
        assert detect_message_type(msg) == "contact"

    def test_location(self):
        msg = _make_message(location=True)
        assert detect_message_type(msg) == "location"

    def test_geo(self):
        """geo 也应识别为 location"""
        msg = _make_message(geo=True)
        assert detect_message_type(msg) == "location"

    def test_poll(self):
        msg = _make_message(poll=True)
        assert detect_message_type(msg) == "poll"

    def test_game(self):
        msg = _make_message(game=True)
        assert detect_message_type(msg) == "game"

    def test_text_message(self):
        """有 text 属性的普通消息"""
        msg = _make_message(text="hello world")
        assert detect_message_type(msg) == "text"

    def test_no_media_is_text(self):
        """没有 media 的消息视为文本"""
        msg = _make_message(media=None, text="hi")
        assert detect_message_type(msg) == "text"

    def test_unknown_media(self):
        """有 media 但无已知类型"""
        msg = _make_message(media=True)  # media 存在但不是 None
        assert detect_message_type(msg) == "unknown"

    def test_photo_priority_over_video(self):
        """photo 在 video 之前检测"""
        msg = _make_message(photo=True, video=True)
        assert detect_message_type(msg) == "photo"

    def test_document_subtypes_priority(self):
        """voice 优先于 audio（都在 document 分支内）"""
        msg = _make_message(document=True, voice=True, audio=True)
        assert detect_message_type(msg) == "voice"

    def test_empty_message(self):
        """空消息对象"""
        msg = _make_message()
        # 没有 text，没有 media → 应该走 text 分支（text=None and media=None → text）
        result = detect_message_type(msg)
        assert result in ("text", "unknown")
