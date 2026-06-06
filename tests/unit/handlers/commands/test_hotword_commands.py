from unittest.mock import AsyncMock

import pytest

from handlers.commands.hotword_commands import handle_hotword_command


class FakeHotwordService:
    def __init__(self):
        self.calls = []

    async def get_rankings(self, channel_name="global", period="day"):
        self.calls.append((channel_name, period))
        return [("月榜热词", 9)]


@pytest.mark.asyncio
async def test_hotword_period_command_shows_global_period(monkeypatch):
    service = FakeHotwordService()
    respond = AsyncMock()
    monkeypatch.setattr(
        "handlers.commands.hotword_commands.get_hotword_service",
        lambda: service,
    )
    monkeypatch.setattr("handlers.commands.hotword_commands.respond_and_delete", respond)

    await handle_hotword_command(object(), "/hot month")

    assert service.calls == [("global", "month")]
    text = respond.await_args.args[1]
    assert "全局月度" in text
