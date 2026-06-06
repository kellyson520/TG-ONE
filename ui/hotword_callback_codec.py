import hashlib
import time
from typing import Optional

_CHANNEL_TOKENS: dict[str, tuple[str, float]] = {}
_TOKEN_TTL_SECONDS = 3600
_TOKEN_MAX_ITEMS = 512


def _prune_tokens(now: float) -> None:
    if len(_CHANNEL_TOKENS) <= _TOKEN_MAX_ITEMS:
        return
    expired = [
        token for token, (_, created_at) in _CHANNEL_TOKENS.items()
        if now - created_at > _TOKEN_TTL_SECONDS
    ]
    for token in expired:
        _CHANNEL_TOKENS.pop(token, None)
    if len(_CHANNEL_TOKENS) > _TOKEN_MAX_ITEMS:
        for token, _ in sorted(_CHANNEL_TOKENS.items(), key=lambda item: item[1][1])[:128]:
            _CHANNEL_TOKENS.pop(token, None)


def register_hotword_channel(channel_name: str) -> str:
    now = time.monotonic()
    token = hashlib.blake2b(channel_name.encode("utf-8"), digest_size=8).hexdigest()
    _CHANNEL_TOKENS[token] = (channel_name, now)
    _prune_tokens(now)
    return token


def resolve_hotword_channel(token: str) -> Optional[str]:
    item = _CHANNEL_TOKENS.get(token)
    if not item:
        return None
    channel_name, created_at = item
    if time.monotonic() - created_at > _TOKEN_TTL_SECONDS:
        _CHANNEL_TOKENS.pop(token, None)
        return None
    return channel_name


def encode_hotword_view_action(channel_name: str, period: str = "day") -> str:
    token = register_hotword_channel(channel_name)
    return f"hotword_view_id:{token}:{period}"
