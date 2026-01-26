import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from handlers.button.callback.modules.rule_nav import callback_switch

# Mock Chat and Event
@pytest.fixture
def mock_event():
    event = AsyncMock()
    event.get_chat.return_value.id = 123456789
    event.answer = AsyncMock()
    return event

@pytest.fixture
def mock_session():
    session = AsyncMock()
    # Important: execute returns a result wrapper, which is synchronous usually
    # But since execute is awaited, return_value is the result object.
    # We need to ensure scalar_one_or_none is not async.
    result_mock = MagicMock()
    session.execute.return_value = result_mock
    return session

@pytest.mark.asyncio
async def test_callback_switch_chat_not_found(mock_event, mock_session):
    # Mock execute result -> None
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    
    # Needs to patch finding by variants also returning None
    with patch('handlers.button.callback.modules.rule_nav.find_chat_by_telegram_id_variants', return_value=None):
        await callback_switch(mock_event, "987654321", mock_session, None, None)
        
    mock_event.answer.assert_called_with("当前聊天不存在")

@pytest.mark.asyncio
async def test_callback_switch_success(mock_event, mock_session):
    # Mock current chat in DB
    current_chat_db = MagicMock()
    current_chat_db.id = 1
    current_chat_db.current_add_id = "old_id"
    
    mock_session.execute.return_value.scalar_one_or_none.return_value = current_chat_db
    
    # Mock target chat found via variants (the new source we are switching to)
    new_source_chat = MagicMock()
    new_source_chat.name = "New Source"
    
    # Mock rules list
    rule_mock = MagicMock()
    rule_mock.source_chat.telegram_chat_id = "987654321"
    mock_session.execute.return_value.scalars.return_value.all.return_value = [rule_mock]

    # Needs container patch for rule_repo access or mock execute result for rules query
    # The code: rules = await s.execute(container.rule_repo.get_rules_for_target_chat(current_chat_db.id))
    # easier to mock container.rule_repo
    with patch('handlers.button.callback.modules.rule_nav.container') as mock_container, \
         patch('handlers.button.callback.modules.rule_nav.find_chat_by_telegram_id_variants', side_effect=[None, new_source_chat]): # 1st call fail (curr chat not via var), 2nd call success (new source)
         # Actually logic:
         # 1. find current_chat_db : we mocked scalar_one_or_none to return it.
         # 2. update current_add_id
         # 3. get rules
         # 4. edit message
         # 5. find source_chat for answer
         
         # Wait, find_chat_by_telegram_id_variants logic in code:
         # if not current_chat_db: find...
         # We returned it via scalar_one_or_none, so find.. not called for current chat.
         # source_chat = find_chat_by_telegram_id_variants(s, rule_id) at end.
         
         with patch('handlers.button.callback.modules.rule_nav.find_chat_by_telegram_id_variants', return_value=new_source_chat):
             message = AsyncMock()
             await callback_switch(mock_event, "987654321", mock_session, message, None)
    
    assert current_chat_db.current_add_id == "987654321"
    mock_session.commit.assert_awaited()
    message.edit.assert_awaited()
    mock_event.answer.assert_awaited_with('已切换到: New Source')
