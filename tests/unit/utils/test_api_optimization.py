
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from utils.network.api_optimization import TelegramAPIOptimizer
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel, Chat

@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Ensure get_entity is also an AsyncMock (implied by AsyncMock parent but setting explicit doesn't hurt)
    return client

@pytest.fixture
def optimizer(mock_client):
    return TelegramAPIOptimizer(mock_client)

@pytest.mark.asyncio
async def test_get_chat_statistics_success(optimizer, mock_client):
    """Test successful retrieval of chat statistics"""
    # Mock entity
    mock_entity = MagicMock(spec=Channel)
    mock_entity.id = 123
    mock_entity.title = "Test Channel"
    mock_client.get_entity.return_value = mock_entity
    
    # Mock full chat response
    mock_full_chat = MagicMock()
    mock_full_chat.full_chat = MagicMock()
    mock_full_chat.full_chat.read_inbox_max_id = 1000
    mock_full_chat.full_chat.participants_count = 500
    
    mock_client.return_value = mock_full_chat
    
    stats = await optimizer.get_chat_statistics(123)
    
    assert stats['chat_id'] == 123
    assert stats['total_messages'] == 1000
    assert stats['participants_count'] == 500
    assert stats['api_method'] == "GetFullChannelRequest"

@pytest.mark.asyncio
async def test_get_chat_statistics_timeout_fallback(optimizer, mock_client):
    """Test fallback when GetFullChannelRequest times out"""
    # Mock entity with some basic info
    mock_entity = MagicMock(spec=Channel)
    mock_entity.id = 456
    mock_entity.title = "Slow Channel"
    mock_entity.participants_count = 100 # Basic info on entity
    mock_entity.username = "slow_channel"
    mock_client.get_entity.return_value = mock_entity
    
    # Mock timeout on Full Request
    mock_client.side_effect = asyncio.TimeoutError
    
    stats = await optimizer.get_chat_statistics(456)
    
    # Should use fallback
    assert stats['chat_id'] == 456
    assert stats['participants_count'] == 100
    assert stats['api_method'] == "EntityFallback"
    assert stats['total_messages'] == 0 # Cannot get this from basic entity

@pytest.mark.asyncio
async def test_get_chat_statistics_get_entity_fail(optimizer, mock_client):
    """Test failure when get_entity fails"""
    mock_client.get_entity.side_effect = Exception("Network Error")
    
    stats = await optimizer.get_chat_statistics(789)
    assert stats == {}
