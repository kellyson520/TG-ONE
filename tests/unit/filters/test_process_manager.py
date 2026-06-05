import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.process import process_forward_rule

@pytest.mark.asyncio
async def test_process_forward_rule_success():
    mock_client = MagicMock()
    mock_event = MagicMock()
    mock_chat_id = 123
    mock_rule = MagicMock()
    mock_rule.id = 1
    
    mock_chain = AsyncMock()
    mock_chain.process.return_value = True
    
    mock_factory = MagicMock()
    mock_factory.create_chain_for_rule.return_value = mock_chain
    
    with patch("filters.process.get_filter_chain_factory", return_value=mock_factory):
        result = await process_forward_rule(mock_client, mock_event, mock_chat_id, mock_rule)
        assert result is True
        mock_chain.process.assert_called_once_with(mock_client, mock_event, mock_chat_id, mock_rule)

@pytest.mark.asyncio
async def test_process_forward_rule_exception():
    mock_client = MagicMock()
    mock_event = MagicMock()
    mock_chat_id = 123
    mock_rule = MagicMock()
    mock_rule.id = 1
    
    with patch("filters.process.get_filter_chain_factory", side_effect=Exception("factory error")):
        result = await process_forward_rule(mock_client, mock_event, mock_chat_id, mock_rule)
        assert result is False
