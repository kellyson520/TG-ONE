"""
去重系统修复验证测试
验证持久化缓存逻辑修复和batch_add方法实现
"""
import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from services.dedup.engine import SmartDeduplicator
from repositories.dedup_repo import DedupRepository


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
        dedup = SmartDeduplicator()
        
        # Mock消息对象
        msg = Mock()
        msg.photo = Mock()
        msg.photo.sizes = [Mock(w=100, h=100, size=1024)]
        msg.message = "测试消息"
        msg.media = None
        msg.grouped_id = None
        
        # Mock持久化缓存
        with patch('services.dedup.engine.get_persistent_cache') as mock_pcache:
            mock_cache = Mock()
            mock_cache.get = Mock(return_value=None)
            mock_cache.set = Mock()
            mock_pcache.return_value = mock_cache
            
            # Mock数据库仓储
            with patch.object(dedup, 'repo') as mock_repo:
                mock_repo.find_by_signature = AsyncMock(return_value=None)
                mock_repo.find_by_file_id_or_hash = AsyncMock(return_value=None)
                
                # 第一次检查(新消息)
                is_dup, reason = await dedup.check_duplicate(msg, 12345)
                
                # 验证: 不是重复
                assert not is_dup, f"新消息被误判为重复: {reason}"
                
                # 验证: 持久化缓存的set方法没有被调用
                # (因为新消息不应该写入PCache)
                assert mock_cache.set.call_count == 0, \
                    "新消息不应该写入持久化缓存"
    
    @pytest.mark.asyncio
    async def test_pcache_written_on_duplicate_detection(self):
        """验证: 检测到重复时才写入持久化缓存"""
        dedup = SmartDeduplicator()
        
        # Mock消息对象
        msg = Mock()
        msg.photo = Mock()
        msg.photo.sizes = [Mock(w=100, h=100, size=1024)]
        msg.message = "重复消息"
        msg.media = None
        msg.grouped_id = None
        
        # 生成签名
        signature = dedup._generate_signature(msg)
        
        # 第一次: 记录到内存缓存
        cache_key = str(12345)
        dedup.time_window_cache[cache_key] = {signature: 1234567890.0}
        
        # Mock持久化缓存
        with patch('services.dedup.engine.get_persistent_cache') as mock_pcache:
            mock_cache = Mock()
            mock_cache.get = Mock(return_value=None)  # PCache未命中
            mock_cache.set = Mock()
            mock_pcache.return_value = mock_cache
            
            # Mock dumps_json
            with patch('services.dedup.engine.dumps_json') as mock_dumps:
                mock_dumps.return_value = '{"ts": 1234567890}'
                
                # 第二次检查(重复消息)
                is_dup, reason = await dedup.check_duplicate(msg, 12345)
                
                # 验证: 是重复
                assert is_dup, "重复消息未被检测到"
                assert "签名重复" in reason or "时间窗口" in reason
                
                # 验证: 持久化缓存的set方法被调用了
                # (因为检测到重复,应该写入PCache加速后续判重)
                assert mock_cache.set.call_count > 0, \
                    "检测到重复时应该写入持久化缓存"
                
                # 验证写入的key格式正确
                call_args = mock_cache.set.call_args_list[0][0]
                key = call_args[0]
                assert key.startswith(f"dedup:sig:{cache_key}:"), \
                    f"PCache key格式错误: {key}"
    
    @pytest.mark.asyncio
    async def test_different_messages_not_confused(self):
        """验证: 不同的消息不会互相干扰"""
        dedup = SmartDeduplicator()
        
        # 消息A
        msg_a = Mock()
        msg_a.photo = Mock()
        msg_a.photo.sizes = [Mock(w=100, h=100, size=1024)]
        msg_a.message = "消息A"
        msg_a.media = None
        msg_a.grouped_id = None
        
        # 消息B (不同的消息)
        msg_b = Mock()
        msg_b.photo = Mock()
        msg_b.photo.sizes = [Mock(w=200, h=200, size=2048)]  # 不同的尺寸
        msg_b.message = "消息B"
        msg_b.media = None
        msg_b.grouped_id = None
        
        # Mock持久化缓存
        with patch('services.dedup.engine.get_persistent_cache') as mock_pcache:
            mock_cache = Mock()
            mock_cache.get = Mock(return_value=None)
            mock_cache.set = Mock()
            mock_pcache.return_value = mock_cache
            
            # Mock数据库仓储
            with patch.object(dedup, 'repo') as mock_repo:
                mock_repo.find_by_signature = AsyncMock(return_value=None)
                mock_repo.find_by_file_id_or_hash = AsyncMock(return_value=None)
                
                # 检查消息A
                is_dup_a, _ = await dedup.check_duplicate(msg_a, 12345)
                assert not is_dup_a, "消息A不应该是重复"
                
                # 检查消息B
                is_dup_b, _ = await dedup.check_duplicate(msg_b, 12345)
                assert not is_dup_b, "消息B不应该是重复(不应该与消息A混淆)"
                
                # 再次检查消息A(应该检测到重复)
                is_dup_a2, reason_a2 = await dedup.check_duplicate(msg_a, 12345)
                assert is_dup_a2, f"消息A第二次应该检测到重复,但结果是: {reason_a2}"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
