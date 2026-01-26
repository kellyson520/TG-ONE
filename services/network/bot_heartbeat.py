import asyncio
import time
from typing import Any, Dict, Optional

from repositories.persistent_cache import dumps_json, get_persistent_cache, loads_json

HEARTBEAT_KEY = "bot_heartbeat"


def get_heartbeat() -> Dict[str, Any]:
    cache = get_persistent_cache()
    s = cache.get(HEARTBEAT_KEY)
    v = loads_json(s) or {}
    ts = float(v.get("ts", 0) or 0)
    age = max(0.0, time.time() - ts) if ts else None
    v["age_seconds"] = age
    return v


def update_heartbeat(
    status: str,
    source: str = "bot",
    details: Optional[Dict[str, Any]] = None,
    ttl: int = 120,
) -> None:
    cache = get_persistent_cache()
    payload: Dict[str, Any] = {
        "status": status,
        "source": source,
        "ts": time.time(),
    }
    if details:
        payload.update(details)
    cache.set(HEARTBEAT_KEY, dumps_json(payload), ttl)


async def start_heartbeat(user_client, bot_client, interval_seconds: int = 30) -> None:
    async def _beat_once():
        ok = False
        try:
            ok = bool(getattr(bot_client, "is_connected", False))
            if ok:
                try:
                    me = await bot_client.get_me()
                    ok = bool(me)
                except Exception:
                    ok = True
        except Exception:
            ok = False
        update_heartbeat("running" if ok else "stopped")

    await _beat_once()
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await _beat_once()
        except asyncio.CancelledError:
            break
        except Exception:
            update_heartbeat("stopped")
