"""idempotency.py — In-memory idempotency key cache.

Prevents duplicate processing when clients retry POST requests.
Keys expire after TTL_SECONDS (default 60s).

In production replace with a Redis SETNX / GET pattern.
"""

import time
from typing import Any, Optional

_CACHE: dict[str, tuple[float, Any]] = {}  # key → (expires_at, cached_response)
TTL_SECONDS = 60


def get_cached(key: str) -> Optional[Any]:
    """Return cached response if key exists and has not expired."""
    entry = _CACHE.get(key)
    if entry is None:
        return None
    expires_at, response = entry
    if time.monotonic() > expires_at:
        del _CACHE[key]
        return None
    return response


def set_cached(key: str, response: Any) -> None:
    """Cache a response under key for TTL_SECONDS."""
    _CACHE[key] = (time.monotonic() + TTL_SECONDS, response)


def cache_size() -> int:
    """Return number of active (non-expired) entries."""
    now = time.monotonic()
    return sum(1 for exp, _ in _CACHE.values() if now <= exp)
