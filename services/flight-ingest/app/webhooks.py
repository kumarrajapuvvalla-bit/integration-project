"""webhooks.py — Outbound webhook registry and async delivery.

Clients register a URL at POST /webhooks/register.
Every accepted ingest event is delivered asynchronously to all registered URLs
with exponential-backoff retries (up to 3 attempts).

In production:
  - Persist registrations to a database
  - Use a proper task queue (Celery / SQS) instead of asyncio tasks
  - Add HMAC-SHA256 signature header for webhook authenticity
"""

import asyncio
import hashlib
import hmac
import logging
import os
import time
from typing import Any

import httpx
from pydantic import BaseModel, HttpUrl

log = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-webhook-secret")

# In-memory registry — survives for the lifetime of the process
_REGISTRY: list[str] = []


# ── Models ────────────────────────────────────────────────────────────────────
class WebhookRegistration(BaseModel):
    url: HttpUrl
    description: str = ""


class WebhookRegistrationResponse(BaseModel):
    url: str
    registered: bool
    total_registered: int


# ── Registry helpers ───────────────────────────────────────────────────────────
def register_url(url: str) -> bool:
    """Register a webhook URL. Returns True if newly added, False if duplicate."""
    if url not in _REGISTRY:
        _REGISTRY.append(url)
        return True
    return False


def list_urls() -> list[str]:
    return list(_REGISTRY)


# ── Delivery ────────────────────────────────────────────────────────────────────
def _sign_payload(body: bytes) -> str:
    """Generate HMAC-SHA256 signature for webhook payload authenticity."""
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


async def deliver_event(event_payload: dict[str, Any], request_id: str) -> None:
    """Fan-out event to all registered webhook URLs with exponential backoff."""
    if not _REGISTRY:
        return

    async def _send(url: str) -> None:
        import json

        body = json.dumps(event_payload).encode()
        sig = _sign_payload(body)
        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": request_id,
            "X-Webhook-Signature": f"sha256={sig}",
            "X-Delivered-At": str(int(time.time())),
        }
        for attempt in range(1, 4):  # up to 3 attempts
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, content=body, headers=headers)
                    if resp.status_code < 500:
                        log.info(
                            "Webhook delivered url=%s status=%d attempt=%d",
                            url, resp.status_code, attempt,
                        )
                        return
                    log.warning(
                        "Webhook server error url=%s status=%d attempt=%d",
                        url, resp.status_code, attempt,
                    )
            except Exception as exc:
                log.warning("Webhook delivery error url=%s attempt=%d: %s", url, attempt, exc)
            await asyncio.sleep(2 ** attempt)  # 2s, 4s, 8s backoff
        log.error("Webhook delivery permanently failed url=%s request_id=%s", url, request_id)

    await asyncio.gather(*[_send(url) for url in _REGISTRY], return_exceptions=True)
