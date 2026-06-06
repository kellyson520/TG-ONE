from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.rule.logic import RuleLogicService


class FakeSession:
    def __init__(self, rule):
        self.rule = rule
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, _model, _rule_id):
        return self.rule

    async def commit(self):
        self.committed = True


class FakeDB:
    def __init__(self, session):
        self.session = session

    def get_session(self):
        return self.session


@pytest.mark.asyncio
async def test_toggle_rule_setting_rejects_invalid_field(monkeypatch):
    session = FakeSession(SimpleNamespace(id=1, enable_sync=False, enable_rule=True))
    container = SimpleNamespace(
        db=FakeDB(session),
        rule_repo=SimpleNamespace(clear_cache=MagicMock()),
        bus=SimpleNamespace(publish=AsyncMock()),
    )
    monkeypatch.setattr(RuleLogicService, "container", property(lambda _self: container))

    result = await RuleLogicService().toggle_rule_setting(1, "does_not_exist")

    assert result["success"] is False
    assert "Invalid field" in result["error"]
    assert session.committed is False
    container.rule_repo.clear_cache.assert_not_called()


@pytest.mark.asyncio
async def test_toggle_rule_setting_requires_value_for_non_boolean(monkeypatch):
    session = FakeSession(SimpleNamespace(id=1, enable_sync=False, delay_seconds=5))
    container = SimpleNamespace(
        db=FakeDB(session),
        rule_repo=SimpleNamespace(clear_cache=MagicMock()),
        bus=SimpleNamespace(publish=AsyncMock()),
    )
    monkeypatch.setattr(RuleLogicService, "container", property(lambda _self: container))

    result = await RuleLogicService().toggle_rule_setting(1, "delay_seconds")

    assert result["success"] is False
    assert "not toggleable" in result["error"]
    assert session.committed is False


@pytest.mark.asyncio
async def test_toggle_rule_setting_updates_cache_and_publishes_event(monkeypatch):
    rule = SimpleNamespace(id=1, enable_sync=False, enable_rule=True)
    session = FakeSession(rule)
    container = SimpleNamespace(
        db=FakeDB(session),
        rule_repo=SimpleNamespace(clear_cache=MagicMock()),
        bus=SimpleNamespace(publish=AsyncMock()),
    )
    monkeypatch.setattr(RuleLogicService, "container", property(lambda _self: container))

    result = await RuleLogicService().toggle_rule_setting(1, "enable_rule")

    assert result == {"success": True, "new_value": False}
    assert rule.enable_rule is False
    assert session.committed is True
    container.rule_repo.clear_cache.assert_called_once_with()
    container.bus.publish.assert_awaited_once_with(
        "RULE_UPDATED",
        {"rule_id": 1, "field": "enable_rule", "action": "update"},
    )
