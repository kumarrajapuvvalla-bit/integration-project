"""pagination.py — Cursor-based event store and pagination helpers.

Stores the last N accepted events in memory and provides cursor-based
pagination via opaque base64-encoded cursors.

In production replace with a TimescaleDB or DynamoDB query.
"""

import base64
import time
from typing import Any, Optional

MAX_STORE = 1000  # maximum events kept in memory
_EVENT_STORE: list[dict[str, Any]] = []


def store_event(event_id: str, flight_id: str, event_type: str, airline: str) -> None:
    """Append an event to the in-memory store."""
    _EVENT_STORE.append(
        {
            "event_id": event_id,
            "flight_id": flight_id,
            "event_type": event_type,
            "airline": airline,
            "ingested_at": int(time.time()),
        }
    )
    if len(_EVENT_STORE) > MAX_STORE:
        _EVENT_STORE.pop(0)  # evict oldest


def _encode_cursor(index: int) -> str:
    return base64.urlsafe_b64encode(str(index).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return 0


def paginate(
    cursor: Optional[str] = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Return a page of events starting from cursor position."""
    limit = max(1, min(limit, 100))  # clamp 1–100
    start = _decode_cursor(cursor) if cursor else 0
    page = _EVENT_STORE[start : start + limit]
    total = len(_EVENT_STORE)
    next_cursor = _encode_cursor(start + limit) if (start + limit) < total else None
    return {
        "items": page,
        "total": total,
        "limit": limit,
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None,
    }


def store_size() -> int:
    return len(_EVENT_STORE)
