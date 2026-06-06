import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.forward_settings_service import ForwardSettingsService

@pytest.fixture
def service():
    # Reset singleton state
    s = ForwardSettingsService()
    s._global_settings = None
    return s

@pytest.fixture
def mock_db_session():
    from core.container import container
    with patch.object(container.db, "session") as mock:
        session = AsyncMock()
        mock.return_value.__aenter__.return_value = session
        yield session

@pytest.mark.asyncio
async def test_get_settings_cache(service, mock_db_session):
    # Setup cache
    service._global_settings = {'allow_text': True}
    
    # Should perform neither DB query nor update
    res = await service.get_global_media_settings()
    assert res == {'allow_text': True}
    mock_db_session.execute.assert_not_called()

@pytest.mark.asyncio
async def test_load_settings_db(service, mock_db_session):
    import json
    # Mock DB result
    mock_result = MagicMock()
    mock_config = MagicMock()
    mock_config.value = json.dumps({'allow_text': False})
    mock_result.scalar_one_or_none.return_value = mock_config
    mock_db_session.execute.return_value = mock_result
    
    res = await service.get_global_media_settings()
    assert res['allow_text'] is False
    assert service._global_settings['allow_text'] is False

@pytest.mark.asyncio
async def test_update_setting(service, mock_db_session):
    # Preload partial settings
    service._global_settings = {'media_types': {'image': True}, 'allow_text': True}
    
    # Mock Select for Save
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock() # existing config
    mock_db_session.execute.return_value = mock_result

    # Update
    await service.update_global_media_setting('allow_text', False)
    
    # Assert
    assert service._global_settings is None # Cache invalidated
    mock_db_session.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_update_setting_reports_save_failure(service):
    settings = {'media_types': {'image': True}, 'allow_text': True}
    service._global_settings = settings
    service._save_global_settings = AsyncMock(return_value=False)

    ok = await service.update_global_media_setting('allow_text', False)

    assert ok is False
    assert settings['allow_text'] is True
    assert service._global_settings is None

@pytest.mark.asyncio
async def test_duration_component_rejects_invalid_inputs(service):
    service._global_settings = {'duration_min_seconds': 0, 'duration_max_seconds': 0}
    service._save_global_settings = AsyncMock(return_value=True)

    assert await service.set_duration_component('middle', 'seconds', 5) is False
    assert await service.set_duration_component('min', 'weeks', 5) is False
    assert await service.set_duration_component('min', 'seconds', 'bad') is False
    service._save_global_settings.assert_not_awaited()

@pytest.mark.asyncio
async def test_toggle_media_type(service, mock_db_session):
    service._global_settings = {'media_types': {'image': True}}
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()
    mock_db_session.execute.return_value = mock_result
    
    await service.toggle_media_type('image')
    
    # Verify commit called (implying save happened)
    mock_db_session.commit.assert_awaited_once()
