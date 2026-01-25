import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from utils.helpers.realtime_stats import RealtimeStatsCache, get_main_menu_stats

@pytest.fixture
def stats_cache():
    return RealtimeStatsCache()

@pytest.mark.asyncio
class TestRealtimeStats:

    async def test_get_forward_stats_cached(self, stats_cache):
        # Setup cache
        stats_cache._cache['forward_stats'] = {'key': 'val'}
        stats_cache._cache_time['forward_stats'] = datetime.now()
        
        # Call
        result = await stats_cache.get_forward_stats(force_refresh=False)
        assert result == {'key': 'val'}

    @patch('utils.helpers.realtime_stats.get_persistent_cache')
    @patch('services.forward_service.forward_service')
    async def test_get_forward_stats_refresh(self, mock_fw_service, mock_pc_getter, stats_cache):
        # Mock services
        mock_fw_service.get_forward_stats = AsyncMock(return_value={'fresh': 'data'})
        
        # Mock persistent cache (returning None to force service call)
        mock_pc = MagicMock()
        mock_pc.get.return_value = None
        mock_pc_getter.return_value = mock_pc
        
        # Call
        result = await stats_cache.get_forward_stats(force_refresh=True)
        
        # Verify
        assert result == {'fresh': 'data'}
        assert stats_cache._cache['forward_stats'] == {'fresh': 'data'}
        mock_fw_service.get_forward_stats.assert_called_once()
        mock_pc.set.assert_called_once() # Should save to persistent cache

    @patch('services.dedup_service.dedup_service')
    async def test_get_dedup_stats(self, mock_dedup_service, stats_cache):
        # Mock service
        mock_dedup_service.get_dedup_config = AsyncMock(return_value={'dedup': 'info'})
        
        # Call with no cache
        result = await stats_cache.get_dedup_stats()
        
        assert result == {'dedup': 'info'}
        mock_dedup_service.get_dedup_config.assert_called_once()

    @patch('services.analytics_service.analytics_service')
    async def test_get_system_stats(self, mock_analytics_service, stats_cache):
        # Mock service
        mock_analytics_service.get_system_status = AsyncMock(return_value={'sys': 'ok'})
        
        # Call
        result = await stats_cache.get_system_stats()
        
        assert result == {'sys': 'ok'}
        mock_analytics_service.get_system_status.assert_called_once()

    async def test_invalidate_cache(self, stats_cache):
        stats_cache._cache['key1'] = 'val1'
        stats_cache._cache_time['key1'] = datetime.now()
        stats_cache._cache['key2'] = 'val2'
        
        # Invalidate specific key
        await stats_cache.invalidate_cache('key1')
        assert 'key1' not in stats_cache._cache
        assert 'key2' in stats_cache._cache
        
        # Invalidate all
        await stats_cache.invalidate_cache()
        assert len(stats_cache._cache) == 0

    async def test_notify_update(self, stats_cache):
        callback = AsyncMock()
        stats_cache.register_update_callback(callback)
        
        await stats_cache._notify_update("test_type", {"data": 1})
        callback.assert_called_once_with("test_type", {"data": 1})

    @patch('utils.helpers.realtime_stats.realtime_stats_cache')
    async def test_get_main_menu_stats(self, mock_global_cache):
        mock_global_cache.get_forward_stats = AsyncMock(return_value={'today': {'total': 10}, 'trend': {}})
        mock_global_cache.get_dedup_stats = AsyncMock(return_value={'stats': {'cached': 5}})
        
        result = await get_main_menu_stats()
        
        assert result['today']['total'] == 10
        assert result['dedup']['cached'] == 5
        assert 'last_updated' in result

    @patch('utils.helpers.realtime_stats.realtime_stats_cache')
    async def test_get_main_menu_stats_error_handling(self, mock_global_cache):
        # Simulate exception during gather
        mock_global_cache.get_forward_stats = AsyncMock(side_effect=Exception("DB Error"))
        mock_global_cache.get_dedup_stats = AsyncMock(return_value={})
        
        result = await get_main_menu_stats()
        
        # Should return structure with defaults despite error
        assert result['today']['total_forwards'] == 0
        assert result['dedup']['cached_signatures'] == 0
