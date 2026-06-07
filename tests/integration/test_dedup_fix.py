"""
去重系统修复验证测试
验证持久化缓存逻辑修复和batch_add方法实现
"""
import asyncio
import time
import pytest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, MagicMock
from services.dedup.engine import SmartDeduplicator
from repositories.dedup_repo import DedupRepository


def build_test_deduplicator() -> SmartDeduplicator:
    """Create a deduplicator with external IO replaced by async mocks."""
    dedup = SmartDeduplicator()
    dedup._repo = MagicMock()
    dedup._repo.exists_media_signature = AsyncMock(return_value=False)
    dedup._repo.exists_video_file_id = AsyncMock(return_value=False)
    dedup._repo.find_by_file_id_or_hash = AsyncMock(return_value=None)
    dedup._repo.check_content_hash_duplicate = AsyncMock(
        return_value=(False, "")
    )
    dedup._repo.batch_add_media_signatures = AsyncMock(return_value=True)
    dedup._repo.load_config = AsyncMock(return_value={})

    dedup._pcache_repo = MagicMock()
    dedup._pcache_repo.get = AsyncMock(return_value=None)
    dedup._pcache_repo.set = AsyncMock(return_value=True)

    dedup.bloom_filter = None
    dedup.hll = None
    dedup.time_window_cache = {}
    dedup.content_hash_cache = {}
    dedup.text_fp_cache = {}
    return dedup


def make_photo_message(photo_id: int, text: str):
    return SimpleNamespace(
        id=photo_id,
        photo=SimpleNamespace(id=photo_id, size=1024),
        video=None,
        document=None,
        sticker=None,
        media=None,
        grouped_id=None,
        message=text,
        text=text,
        type="photo",
    )


def make_text_message(message_id: int, text: str):
    return SimpleNamespace(
        id=message_id,
        photo=None,
        video=None,
        document=None,
        sticker=None,
        media=None,
        grouped_id=None,
        message=text,
        text=text,
        type="text",
    )


async def stop_flush_worker(dedup: SmartDeduplicator):
    if dedup._flush_task and not dedup._flush_task.done():
        dedup._flush_task.cancel()
        await asyncio.gather(dedup._flush_task, return_exceptions=True)


class TestDedupFix:
    """测试去重系统关键修复"""

    @pytest.mark.asyncio
    async def test_batch_add_method_exists(self):
        """验证: DedupRepository.batch_add 方法存在且可调用"""
        # 创建mock数据库
        mock_db = Mock()
        repo = DedupRepository(mock_db)

        # 验证方法存在
        assert hasattr(repo, 'batch_add')
        assert callable(repo.batch_add)

        # 验证方法签名
        import inspect
        sig = inspect.signature(repo.batch_add)
        params = list(sig.parameters.keys())
        # 注意: inspect.signature 不包含 self 参数
        assert 'records' in params, f"Expected 'records' in {params}"

    @pytest.mark.asyncio
    async def test_pcache_not_written_for_new_messages(self):
        """验证: 新消息不会自动写入持久化缓存"""
        dedup = build_test_deduplicator()
        msg = make_photo_message(1001, "测试消息")

        try:
            # 第一次检查(新消息)
            is_dup, reason = await dedup.check_duplicate(msg, 12345)

            # 验证: 不是重复
            assert not is_dup, f"新消息被误判为重复: {reason}"

            # 验证: 持久化缓存的set方法没有被调用
            # (因为新消息不应该写入PCache)
            dedup._pcache_repo.set.assert_not_awaited()
        finally:
            await stop_flush_worker(dedup)

    @pytest.mark.asyncio
    async def test_pcache_written_on_duplicate_detection(self):
        """验证: 检测到重复时才写入持久化缓存"""
        dedup = build_test_deduplicator()
        msg = make_photo_message(2001, "重复消息")

        # 生成签名
        from services.dedup import tools
        signature = tools.generate_signature(msg)

        # 第一次: 记录到内存缓存
        cache_key = str(12345)
        dedup.time_window_cache[cache_key] = {signature: time.time()}

        # 第二次检查(重复消息)
        is_dup, reason = await dedup.check_duplicate(msg, 12345)

        # 验证: 是重复
        assert is_dup, "重复消息未被检测到"
        assert "签名重复" in reason or "时间窗口" in reason

        # 验证: 持久化缓存的set方法被调用了
        # (因为检测到重复,应该写入PCache加速后续判重)
        dedup._pcache_repo.set.assert_awaited()

        # 验证写入的key格式正确
        call_args = dedup._pcache_repo.set.call_args_list[0]
        key = call_args.args[0]
        assert key == f"sig:{cache_key}:{signature}", \
            f"PCache key格式错误: {key}"

    @pytest.mark.asyncio
    async def test_signature_database_duplicate_backfills_pcache(self):
        """验证: 签名数据库命中时会回填持久化缓存"""
        dedup = build_test_deduplicator()
        msg = make_photo_message(2101, "数据库重复消息")

        from services.dedup import tools
        signature = tools.generate_signature(msg)
        dedup._repo.exists_media_signature.return_value = True

        is_dup, reason = await dedup.check_duplicate(msg, 12345)

        assert is_dup, f"数据库重复消息未被检测到: {reason}"
        assert "数据库" in reason

        call_args = dedup._pcache_repo.set.call_args_list[0]
        key = call_args.args[0]
        assert key == f"sig:12345:{signature}", \
            f"PCache key格式错误: {key}"

    @pytest.mark.asyncio
    async def test_content_hash_database_duplicate_backfills_pcache(self):
        """验证: 内容哈希数据库命中时会回填持久化缓存"""
        dedup = build_test_deduplicator()
        msg = make_text_message(2201, "这是一条用于内容哈希去重的重复消息")

        from services.dedup import tools
        content_hash = tools.generate_content_hash(msg)
        dedup._repo.check_content_hash_duplicate.return_value = (
            True,
            "content dup",
        )

        is_dup, reason = await dedup.check_duplicate(msg, 12345)

        assert is_dup, f"内容哈希重复消息未被检测到: {reason}"
        assert "内容重复" in reason

        call_args = dedup._pcache_repo.set.call_args_list[0]
        key = call_args.args[0]
        assert key == f"hash:12345:{content_hash}", \
            f"PCache key格式错误: {key}"

    @pytest.mark.asyncio
    async def test_different_messages_not_confused(self):
        """验证: 不同的消息不会互相干扰"""
        dedup = build_test_deduplicator()

        # 消息A
        msg_a = make_photo_message(3001, "消息A")

        # 消息B (不同的消息)
        msg_b = make_photo_message(3002, "消息B")

        try:
            # 检查消息A
            is_dup_a, _ = await dedup.check_duplicate(msg_a, 12345)
            assert not is_dup_a, "消息A不应该是重复"

            # 检查消息B
            is_dup_b, _ = await dedup.check_duplicate(msg_b, 12345)
            assert not is_dup_b, "消息B不应该是重复(不应该与消息A混淆)"

            # 再次检查消息A(应该检测到重复)
            is_dup_a2, reason_a2 = await dedup.check_duplicate(msg_a, 12345)
            assert is_dup_a2, f"消息A第二次应该检测到重复,但结果是: {reason_a2}"
        finally:
            await stop_flush_worker(dedup)


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
