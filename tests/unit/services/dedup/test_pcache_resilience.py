import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.dedup.engine import SmartDeduplicator
from services.dedup.strategies.album import AlbumStrategy
from services.dedup.strategies.video import VideoStrategy


def build_dedup() -> SmartDeduplicator:
    dedup = SmartDeduplicator()
    dedup._repo = MagicMock()
    dedup._repo.exists_media_signature = AsyncMock(return_value=False)
    dedup._repo.exists_video_file_id = AsyncMock(return_value=False)
    dedup._repo.check_content_hash_duplicate = AsyncMock(
        return_value=(False, "")
    )
    dedup._repo.find_by_file_id_or_hash = AsyncMock(return_value=None)
    dedup._repo.batch_add_media_signatures = AsyncMock(return_value=True)
    dedup._repo.load_config = AsyncMock(return_value={})

    dedup._pcache_repo = MagicMock()
    dedup._pcache_repo.get = AsyncMock(return_value=None)
    dedup._pcache_repo.set = AsyncMock(
        side_effect=RuntimeError("pcache unavailable")
    )

    dedup.bloom_filter = None
    dedup.hll = None
    dedup.time_window_cache = {}
    dedup.content_hash_cache = {}
    dedup.text_fp_cache = {}
    return dedup


async def stop_flush_worker(dedup: SmartDeduplicator):
    if dedup._flush_task and not dedup._flush_task.done():
        dedup._flush_task.cancel()
        await asyncio.gather(dedup._flush_task, return_exceptions=True)


def make_pcache_get_unavailable(dedup: SmartDeduplicator):
    dedup._pcache_repo.get.side_effect = RuntimeError(
        "pcache lookup unavailable"
    )
    dedup._pcache_repo.set.side_effect = None
    dedup._pcache_repo.set.return_value = True


def make_photo_message(message_id: int):
    return SimpleNamespace(
        id=message_id,
        photo=SimpleNamespace(id=message_id, size=1024),
        video=None,
        document=None,
        sticker=None,
        media=None,
        grouped_id=None,
        message="photo",
        text="photo",
        type="photo",
    )


def make_video_message(message_id: int):
    return SimpleNamespace(
        id=message_id,
        video=SimpleNamespace(
            id=message_id,
            size=1024,
            duration=10,
            w=1280,
            h=720,
        ),
        photo=None,
        document=None,
        sticker=None,
        media=None,
        grouped_id=None,
        message="video",
        text="video",
        type="video",
    )


def make_sticker_message(message_id: int):
    return SimpleNamespace(
        id=message_id,
        sticker=SimpleNamespace(id=message_id),
        video=None,
        photo=None,
        document=None,
        media=None,
        grouped_id=None,
        message="",
        text="",
        type="sticker",
    )


def make_text_message(message_id: int):
    text = "这是一条用于全局共振去重的文本消息"
    return SimpleNamespace(
        id=message_id,
        sticker=None,
        video=None,
        photo=None,
        document=None,
        media=None,
        grouped_id=None,
        message=text,
        text=text,
        type="text",
    )


def make_album_message(message_id: int):
    return SimpleNamespace(
        id=message_id,
        photo=SimpleNamespace(id=message_id, size=1024),
        video=None,
        document=None,
        sticker=None,
        media=None,
        grouped_id=777,
        message="album item",
        text="album item",
        type="photo",
    )


@pytest.mark.asyncio
async def test_video_file_id_duplicate_survives_pcache_backfill_failure():
    dedup = build_dedup()
    dedup._repo.exists_video_file_id.return_value = True

    is_dup, reason = await dedup.check_duplicate(
        make_video_message(1001),
        12345,
    )

    assert is_dup is True
    assert "FileID" in reason


@pytest.mark.asyncio
async def test_signature_duplicate_survives_pcache_lookup_failure():
    dedup = build_dedup()
    make_pcache_get_unavailable(dedup)

    msg = make_photo_message(1101)
    from services.dedup import tools
    signature = tools.generate_signature(msg)
    dedup.time_window_cache[str(12345)] = {signature: time.time()}

    is_dup, reason = await dedup.check_duplicate(msg, 12345)

    assert is_dup is True
    assert "时间窗口" in reason


@pytest.mark.asyncio
async def test_content_duplicate_survives_pcache_lookup_failure():
    dedup = build_dedup()
    make_pcache_get_unavailable(dedup)
    dedup._repo.check_content_hash_duplicate.return_value = (
        True,
        "content duplicate",
    )

    is_dup, reason = await dedup.check_duplicate(
        make_text_message(1201),
        12345,
    )

    assert is_dup is True
    assert "内容重复" in reason


@pytest.mark.asyncio
async def test_video_file_id_duplicate_survives_pcache_lookup_failure():
    dedup = build_dedup()
    make_pcache_get_unavailable(dedup)
    dedup.strategies = [VideoStrategy()]
    dedup._repo.exists_video_file_id.return_value = True

    is_dup, reason = await dedup.check_duplicate(
        make_video_message(1301),
        12345,
    )

    assert is_dup is True
    assert "FileID" in reason


@pytest.mark.asyncio
async def test_sticker_duplicate_survives_pcache_backfill_failure():
    dedup = build_dedup()
    dedup._repo.exists_media_signature.return_value = True

    is_dup, reason = await dedup.check_duplicate(
        make_sticker_message(2001),
        12345,
    )

    assert is_dup is True
    assert "表情包重复" in reason


@pytest.mark.asyncio
async def test_sticker_duplicate_survives_pcache_lookup_failure():
    dedup = build_dedup()
    make_pcache_get_unavailable(dedup)
    dedup._repo.exists_media_signature.return_value = True

    is_dup, reason = await dedup.check_duplicate(
        make_sticker_message(2101),
        12345,
    )

    assert is_dup is True
    assert "表情包重复" in reason


@pytest.mark.asyncio
async def test_global_resonance_survives_pcache_backfill_failure():
    dedup = build_dedup()
    dedup.strategies = []
    dedup._repo.check_content_hash_duplicate.return_value = (
        True,
        "global duplicate",
    )

    try:
        is_dup, reason = await dedup.check_duplicate(
            make_text_message(3001),
            12345,
            {"enable_global_search": True},
        )
    finally:
        await stop_flush_worker(dedup)

    assert is_dup is True
    assert "全局内容传播命中" in reason


@pytest.mark.asyncio
async def test_global_resonance_survives_pcache_lookup_failure():
    dedup = build_dedup()
    make_pcache_get_unavailable(dedup)
    dedup.strategies = []
    dedup._repo.check_content_hash_duplicate.return_value = (
        True,
        "global duplicate",
    )

    try:
        is_dup, reason = await dedup.check_duplicate(
            make_text_message(3101),
            12345,
            {"enable_global_search": True},
        )
    finally:
        await stop_flush_worker(dedup)

    assert is_dup is True
    assert "全局内容传播命中" in reason


@pytest.mark.asyncio
async def test_album_state_cache_failure_degrades_to_normal_flow():
    dedup = build_dedup()

    try:
        is_dup, reason = await dedup.check_duplicate(
            make_album_message(4001),
            12345,
        )
    finally:
        await stop_flush_worker(dedup)

    assert is_dup is False
    assert reason == "无重复"


@pytest.mark.asyncio
async def test_album_state_lookup_failure_degrades_to_normal_flow():
    dedup = build_dedup()
    make_pcache_get_unavailable(dedup)
    dedup.strategies = [AlbumStrategy()]

    try:
        is_dup, reason = await dedup.check_duplicate(
            make_album_message(4101),
            12345,
        )
    finally:
        await stop_flush_worker(dedup)

    assert is_dup is False
    assert reason == "无重复"


@pytest.mark.asyncio
async def test_album_corrupt_state_cache_degrades_to_normal_flow():
    dedup = build_dedup()
    dedup.strategies = [AlbumStrategy()]
    dedup._pcache_repo.get.return_value = "{not-json"
    dedup._pcache_repo.set.side_effect = None
    dedup._pcache_repo.set.return_value = True

    try:
        is_dup, reason = await dedup.check_duplicate(
            make_album_message(4201),
            12345,
        )
    finally:
        await stop_flush_worker(dedup)

    assert is_dup is False
    assert reason == "无重复"
