from handlers.button.strategies.hotword import parse_hotword_view_payload


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
