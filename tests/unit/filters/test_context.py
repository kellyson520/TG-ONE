import pytest
from unittest.mock import MagicMock, patch
from filters.context import MessageContext

@pytest.fixture
def mock_event():
    event = MagicMock()
    event.message.text = "test message"
    event.message.grouped_id = None
    event.message.buttons = None
    return event

def test_message_context_init(mock_event):
    client = MagicMock()
    chat_id = 123
    rule = MagicMock()
    
    with patch("core.context.trace_id_var") as mock_trace_id_var:
        mock_trace_id_var.get.return_value = "custom-trace"
        context = MessageContext(client, mock_event, chat_id, rule)
        
        assert context.client == client
        assert context.event == mock_event
        assert context.chat_id == chat_id
        assert context.rule == rule
        assert context.trace_id == "custom-trace"
        assert context.original_message_text == "test message"
        assert context.message_text == "test message"
        assert context.should_forward is True
        assert context.is_media_group is False

def test_message_context_trace_id_generation(mock_event):
    client = MagicMock()
    rule = MagicMock()
    
    with patch("core.context.trace_id_var") as mock_trace_id_var:
        mock_trace_id_var.get.return_value = "-"
        context = MessageContext(client, mock_event, 123, rule)
        
        assert len(context.trace_id) == 8
        assert context.correlation_id == context.trace_id

def test_message_context_clone(mock_event):
    client = MagicMock()
    rule = MagicMock()
    context = MessageContext(client, mock_event, 123, rule)
    context.message_text = "modified"
    
    cloned = context.clone()
    assert cloned.message_text == "modified"
    assert cloned.trace_id == context.trace_id
    
    cloned.message_text = "cloned-modified"
    assert context.message_text == "modified"

def test_message_context_correlation_id(mock_event):
    context = MessageContext(MagicMock(), mock_event, 123, MagicMock())
    context.correlation_id = "new-id"
    assert context.trace_id == "new-id"
    assert context.correlation_id == "new-id"

def test_message_context_media_group(mock_event):
    mock_event.message.grouped_id = 999
    context = MessageContext(MagicMock(), mock_event, 123, MagicMock())
    assert context.is_media_group is True
    assert context.media_group_id == 999
