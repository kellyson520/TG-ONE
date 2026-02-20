import pytest
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock
from services.analytics_service import AnalyticsService
from datetime import datetime
from core.helpers.realtime_stats import realtime_stats_cache

@pytest.fixture
def analytics_service():
    return AnalyticsService()

@pytest.mark.asyncio
async def test_get_analytics_overview(analytics_service):
    mock_task_repo = AsyncMock()
    mock_task_repo.get_rule_stats.return_value = {
        'total_rules': 10,
        'active_rules': 5,
        'total_chats': 20
    }
    
    mock_container = MagicMock()
    mock_container.task_repo = mock_task_repo
    
    # Patch the property directly on the instance
    with patch.object(AnalyticsService, 'container', new_callable=PropertyMock) as mock_container_prop:
        mock_container_prop.return_value = mock_container
        
        with patch('services.forward_service.forward_service.get_forward_stats', new_callable=AsyncMock) as mock_get_forward_stats, \
             patch('services.dedup.engine.smart_deduplicator.get_stats') as mock_get_dedup_stats:
            
            mock_get_forward_stats.return_value = {
                'today': {'total_forwards': 100}
            }
            mock_get_dedup_stats.return_value = {
                'cached_signatures': 500
            }
            
            # Mock stats_repo to prevent await failure in get_detailed_stats
            mock_stats_repo = AsyncMock()
            mock_stats_repo.get_hourly_trend.return_value = []
            mock_container.stats_repo = mock_stats_repo
            
            # Mock stats_repo related methods
            with patch.object(analytics_service, 'get_daily_summary', new_callable=AsyncMock) as mock_daily:
                mock_daily.return_value = {'total_forwards': 50}
                result = await analytics_service.get_analytics_overview()
            
            assert result['overview']['total_rules'] == 10
            assert result['overview']['active_rules'] == 5
            assert result['forward_stats']['total_forwards'] == 100
            assert result['dedup_stats']['cached_signatures'] == 500

@pytest.mark.asyncio
async def test_get_system_status(analytics_service):
    mock_container = MagicMock()
    mock_container.bot_client.is_connected.return_value = True
    mock_container.user_client.is_connected.return_value = True
    
    with patch.object(AnalyticsService, 'container', new_callable=PropertyMock) as mock_container_prop, \
         patch('models.models.get_db_health') as mock_db_health, \
         patch('services.analytics_service.get_heartbeat') as mock_heartbeat, \
         patch('services.dedup.engine.smart_deduplicator.config', PropertyMock(return_value={'enable_time_window': True})):
        
        mock_container_prop.return_value = mock_container
        mock_db_health.return_value = {'connected': True}
        mock_heartbeat.return_value = {'status': 'running', 'age_seconds': 10}
        
        result = await analytics_service.get_system_status()
        
        assert result['db'] == 'running'
        assert result['bot'] == 'running'
        assert result['user'] == 'running'
        assert result['dedup'] == 'running'

@pytest.mark.asyncio
async def test_get_performance_metrics(analytics_service):
    mock_task_repo = AsyncMock()
    mock_task_repo.get_queue_status.return_value = {
        'active_queues': 2,
        'pending_tasks': 50,
        # Error rate is computed by logic, not directly from repo return if logic exists
    }
    
    mock_container = MagicMock()
    mock_container.task_repo = mock_task_repo
    
    # Mock database session for TPS/response time calculation
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = MagicMock(count=10, avg_time=500)
    mock_session.execute.return_value = mock_result
    mock_container.db.get_session.return_value.__aenter__.return_value = mock_session
    
    with patch.object(AnalyticsService, 'container', new_callable=PropertyMock) as mock_container_prop:
        mock_container_prop.return_value = mock_container
        
        # Use patch.object on the live instance for Robustness
        with patch.object(realtime_stats_cache, 'get_system_stats', new_callable=AsyncMock) as mock_get_sys_stats, \
             patch.object(realtime_stats_cache, 'get_forward_stats', new_callable=AsyncMock) as mock_get_fwd_stats:
            
            mock_get_sys_stats.return_value = {
                'system_resources': {'cpu_percent': 10, 'memory_percent': 20}
            }
            # Mock forward stats for success rate calculation
            mock_get_fwd_stats.return_value = {
                "today": {
                    "total_forwards": 100,
                    "error_count": 1
                }
            }
            
            result = await analytics_service.get_performance_metrics()
            
            assert result['system_resources']['cpu_percent'] == 10
            assert result['queue_status']['pending_tasks'] == 50
            # Success rate 99% -> Error rate 1.0% -> "1.0%"
            assert result['queue_status']['error_rate'] == "1.0%"
            # Verify TPS calculation (10 / 600 = 0.0166... -> 0.02)
            assert result['performance']['current_tps'] == 0.02

@pytest.mark.asyncio
async def test_search_records(analytics_service):
    from models.models import RuleLog, ForwardRule
    
    # 1. Setup Mock Rule
    mock_rule = MagicMock(spec=ForwardRule)
    mock_rule.id = 101
    
    mock_source_chat = MagicMock()
    mock_source_chat.title = "Source Chat Name"
    mock_source_chat.name = None
    mock_source_chat.username = None
    
    mock_target_chat = MagicMock()
    mock_target_chat.title = "Target Chat Name"
    mock_target_chat.name = None
    mock_target_chat.username = None
    
    mock_rule.source_chat = mock_source_chat
    mock_rule.target_chat = mock_target_chat
    
    # 2. Mock DB Session
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_rule]
    mock_session.execute.return_value = mock_result
    
    mock_container = MagicMock()
    mock_container.db.get_session.return_value.__aenter__.return_value = mock_session
    
    # 3. Patch and execute
    with patch.object(AnalyticsService, 'container', new_callable=PropertyMock) as mock_container_prop, \
         patch.object(analytics_service.bridge, 'query_unified', new_callable=AsyncMock) as mock_query_unified:
        
        mock_container_prop.return_value = mock_container
        mock_query_unified.return_value = [{
            'id': 1,
            'rule_id': 101,
            'action': 'forwarded',
            'message_text': 'Hello World',
            'created_at': datetime.now()
        }]
        
        result = await analytics_service.search_records(query='Hello')
        
        assert 'records' in result
        assert len(result['records']) == 1
        assert result['records'][0]['source_chat'] == "Source Chat Name"
        assert result['records'][0]['target_chat'] == "Target Chat Name"
        assert result['records'][0]['source_chat_id'] == "Source Chat Name"
