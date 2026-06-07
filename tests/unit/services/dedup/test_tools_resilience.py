import logging

from services.dedup import tools


class BrokenMediaMessage:
    @property
    def photo(self):
        raise RuntimeError("photo attribute unavailable")


def test_generate_signature_failure_logs_and_degrades(caplog):
    caplog.set_level(logging.DEBUG, logger=tools.__name__)

    result = tools.generate_signature(BrokenMediaMessage())

    assert result is None
    assert "强特征签名生成失败" in caplog.text
    assert "photo attribute unavailable" in caplog.text


def test_generate_content_hash_failure_logs_and_degrades(monkeypatch, caplog):
    def fail_fingerprint(message_obj):
        raise RuntimeError("fingerprint unavailable")

    monkeypatch.setattr(tools, "generate_v3_fingerprint", fail_fingerprint)
    caplog.set_level(logging.DEBUG, logger=tools.__name__)

    result = tools.generate_content_hash(object())

    assert result is None
    assert "内容哈希生成失败" in caplog.text
    assert "fingerprint unavailable" in caplog.text


def test_video_partial_hash_failure_logs_and_degrades(
    tmp_path,
    monkeypatch,
    caplog,
):
    video_file = tmp_path / "video.bin"
    video_file.write_bytes(b"video bytes")

    def fail_open(*args, **kwargs):
        raise RuntimeError("read unavailable")

    monkeypatch.setattr("builtins.open", fail_open)
    caplog.set_level(logging.DEBUG, logger=tools.__name__)

    result = tools.calculate_video_partial_file_hash(str(video_file))

    assert result is None
    assert "视频部分哈希计算失败" in caplog.text
    assert str(video_file) in caplog.text
    assert "read unavailable" in caplog.text
