import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telethon.errors import MessageNotModifiedError

from handlers.button.strategies.hotword import parse_hotword_view_payload
from ui.hotword_callback_codec import _CHANNEL_TOKENS, encode_hotword_view_action


def test_parse_hotword_view_payload_supports_colon_in_channel_name():
    channel, period = parse_hotword_view_payload("hotword_view:News:Crypto:month")

    assert channel == "News:Crypto"
    assert period == "month"


def test_parse_hotword_view_payload_defaults_invalid_period_to_day():
    channel, period = parse_hotword_view_payload("hotword_view:News:Crypto")

    assert channel == "News:Crypto"
    assert period == "day"


def test_parse_hotword_view_payload_uses_extra_data():
    channel, period = parse_hotword_view_payload(
        "hotword_view:ignored",
        ["Channel:From:Extra", "year"],
    )

    assert channel == "Channel:From:Extra"
    assert period == "year"


def test_parse_hotword_view_payload_rejoins_split_extra_data_channel():
    channel, period = parse_hotword_view_payload(
        "new_menu:hotword_view:Channel:From:Extra:year",
        ["Channel", "From", "Extra", "year"],
    )

    assert channel == "Channel:From:Extra"
    assert period == "year"


def test_hotword_view_token_payload_round_trip_for_long_channel_name():
    long_channel = "小说🌸小说搜索🔍全网成人小说🌸完本小说"
    action = encode_hotword_view_action(long_channel, "month")

    channel, period = parse_hotword_view_payload(action)

    assert len(action.encode("utf-8")) <= 64
    assert channel == long_channel
    assert period == "month"


def test_hotword_view_token_payload_resolves_after_new_menu_split():
    long_channel = "小说🌸小说搜索🔍全网成人小说🌸完本小说"
    action = encode_hotword_view_action(long_channel, "month")
    _, token, period = action.split(":")

    channel, parsed_period = parse_hotword_view_payload(
        f"new_menu:{action}",
        [token, period],
    )

    assert channel == long_channel
    assert parsed_period == "month"


def test_hotword_view_token_payload_survives_memory_mapping_loss():
    long_channel = "小说🌸小说搜索🔍全网成人小说🌸完本小说"
    action = encode_hotword_view_action(long_channel, "year")
    _, token, _ = action.split(":")
    _CHANNEL_TOKENS.clear()

    channel, period = parse_hotword_view_payload(action)

    assert channel == token
    assert period == "year"


@pytest.mark.asyncio
async def test_hotword_main_logs_message_not_modified(monkeypatch, caplog):
    from handlers.button.strategies import hotword as module

    event = SimpleNamespace(
        data=b"hotword_main",
        edit=AsyncMock(side_effect=MessageNotModifiedError(request=None)),
        answer=AsyncMock(),
    )
    service = SimpleNamespace(get_rankings=AsyncMock(return_value=[]))
    rendered = SimpleNamespace(text="same text", buttons=[])

    monkeypatch.setattr(
        "services.hotword_service.get_hotword_service",
        lambda: service,
    )
    monkeypatch.setattr(
        "ui.renderers.hotword_renderer.hotword_renderer.render_global_rankings",
        lambda *args, **kwargs: rendered,
    )

    with caplog.at_level(logging.DEBUG, logger=module.__name__):
        await module.HotwordMenuStrategy().handle(
            event,
            "hotword_main",
            data="hotword_main",
            extra_data=[],
        )

    event.answer.assert_awaited_once()
    assert "热词菜单内容未变化" in caplog.text
    assert "action=hotword_main" in caplog.text
