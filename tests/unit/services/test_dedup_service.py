import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.dedup_service import dedup_service
from models.models import MediaSignature

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestDedupService:
    @pytest.fixture(autouse=True)
    async def setup_dedup(self):
        # 确保每个测试都重置配置
        from services.dedup.engine import smart_deduplicator
        await smart_deduplicator.reset_to_defaults()
        smart_deduplicator.time_window_cache.clear()
        smart_deduplicator.content_hash_cache.clear()
        yield

    async def test_get_dedup_config(self):
        config = await dedup_service.get_dedup_config()
        assert "config" in config
        assert "stats" in config
        assert config["config"]["enable_time_window"] is True

    async def test_update_config(self):
        result = await dedup_service.update_config({"time_window_hours": 48})
        assert result["success"] is True
        config = await dedup_service.get_dedup_config()
        assert config["config"]["time_window_hours"] == 48

    async def test_toggle_feature(self):
        # 切换开关
        await dedup_service.toggle_feature("time_window", False)
        config = await dedup_service.get_dedup_config()
        assert config["config"]["enable_time_window"] is False

    async def test_set_time_window(self):
        # 测试合法值
        await dedup_service.set_time_window(10)
        config = await dedup_service.get_dedup_config()
        assert config["config"]["time_window_hours"] == 10

        # 测试异常值
        result = await dedup_service.set_time_window(200)
        assert result["success"] is False

    async def test_clear_all_cache(self):
        # 模拟一些缓存数据
        from services.dedup.engine import smart_deduplicator
        smart_deduplicator.time_window_cache = {1: {"sig1": 123456}}
        
        result = await dedup_service.clear_all_cache()
        assert result["success"] is True
        assert result["cleared_items"]["signatures"] == 1
        assert len(smart_deduplicator.time_window_cache) == 0

    @pytest.mark.skip(reason="Transaction isolation issue between service commit and test session")
    async def test_record_signature(self, db):
        # 准备一个 Mock 消息对象
        message = MagicMock()
        message.id = 123
        message.message = "Hello World"
        message.media = MagicMock()
        message.photo = None
        message.video = None
        message.document = None
        
        # Mock commit prevents transaction closure, ensuring test can verify data in same session
        db.commit = AsyncMock()
        
        # 关联数据库到服务
        dedup_service.set_db(MagicMock(session=lambda: db))
        
        # 准备带媒体的消息
        file_mock = MagicMock()
        file_mock.id = "file_123"
        message.media = MagicMock()
        message.file = file_mock
        
        # 模拟 EventBus 调用或者直接调用
        with patch("services.dedup.engine.smart_deduplicator._record_message", new_callable=AsyncMock), \
             patch("services.dedup_service.bloom_filter_service"):
            await dedup_service.record_signature(1001, message)
        
        # 验证数据库中是否有记录
        # 注意：dedup_service.py:250 写入了 MediaSignature
        from sqlalchemy import select
        await db.flush()
        res = await db.execute(select(MediaSignature).filter_by(chat_id="1001"))
        sig = res.scalar_one_or_none()
        assert sig is not None
        assert sig.signature == "file_123"

    async def test_is_duplicate(self):
        message = MagicMock()
        message.message = "Duplicate content"
        message.id = 1
        message.media = None
        
        # 1. 第一次检查，不重复
        is_dup = await dedup_service.is_duplicate(1001, message)
        assert is_dup is False
        
        # 2. 记录签名（模拟）
        # 我们直接调用 smart_deduplicator 的方法记录，因为 dedup_service.record_signature 内部逻辑较多
        from services.dedup.engine import smart_deduplicator
        await smart_deduplicator._record_message(message, 1001, "sig123", "hash123")
        
        # 3. 再次检查（此时应该基于缓存发现重复）
        # 需要 Mock Bloom Filter，否则会因 Bloom Filter 未命中而直接返回 False
        with patch("services.dedup_service.bloom_filter_service") as mock_bf, \
             patch("services.dedup.engine.smart_deduplicator._generate_signature", return_value="sig123"):
            
            mock_bf.__contains__.return_value = True
            
            is_dup = await dedup_service.is_duplicate(1001, message)
            assert is_dup is True
