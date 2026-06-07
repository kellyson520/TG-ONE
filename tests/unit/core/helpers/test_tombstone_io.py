import logging
from pathlib import Path

import pytest

from core.helpers import tombstone as tombstone_module


def build_manager(tmp_path):
    manager = tombstone_module.TombstoneManager.__new__(
        tombstone_module.TombstoneManager
    )
    manager._tombstone_path = str(tmp_path / "tombstone_state.bin")
    return manager


def test_write_to_disk_handles_text_json_and_uses_atomic_replace(
    tmp_path,
    monkeypatch,
):
    manager = build_manager(tmp_path)
    replace_calls = []
    real_replace = tombstone_module.os.replace

    def recording_replace(src, dst):
        replace_calls.append((src, dst))
        real_replace(src, dst)

    monkeypatch.setattr(
        tombstone_module.json,
        "dumps",
        lambda state: '{"component":{"value":1}}',
    )
    monkeypatch.setattr(tombstone_module.os, "replace", recording_replace)

    manager._write_to_disk({"component": {"value": 1}})

    assert replace_calls
    src, dst = replace_calls[0]
    assert Path(src).parent == tmp_path
    assert dst == str(tmp_path / "tombstone_state.bin")
    assert (tmp_path / "tombstone_state.bin").read_bytes() == (
        b'{"component":{"value":1}}'
    )


def test_write_to_disk_logs_missing_temp_cleanup(
    tmp_path,
    monkeypatch,
    caplog,
):
    manager = build_manager(tmp_path)

    def fail_replace(src, dst):
        raise RuntimeError("replace failed")

    def missing_unlink(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(tombstone_module.os, "replace", fail_replace)
    monkeypatch.setattr(tombstone_module.os, "unlink", missing_unlink)
    caplog.set_level(logging.DEBUG, logger="core.helpers.tombstone")

    with pytest.raises(RuntimeError, match="replace failed"):
        manager._write_to_disk({"component": {"value": 1}})

    assert "墓碑临时文件已不存在" in caplog.text
