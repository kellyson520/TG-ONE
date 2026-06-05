import threading
import time
from contextlib import contextmanager
from typing import Iterator


_lock = threading.Lock()
_state_lock = threading.Lock()
_owner = ""
_started_at = 0.0


def is_maintenance_active() -> bool:
    with _state_lock:
        return bool(_owner)


def maintenance_owner() -> str:
    with _state_lock:
        if not _owner:
            return ""
        return f"{_owner} ({time.time() - _started_at:.1f}s)"


@contextmanager
def try_maintenance(owner: str) -> Iterator[bool]:
    global _owner, _started_at

    acquired = _lock.acquire(blocking=False)
    if not acquired:
        yield False
        return

    with _state_lock:
        _owner = owner
        _started_at = time.time()

    try:
        yield True
    finally:
        with _state_lock:
            _owner = ""
            _started_at = 0.0
        _lock.release()
