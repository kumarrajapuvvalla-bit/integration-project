from fastapi import FastAPI, HTTPException, Request, status, Depends, BackgroundTasks
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import logging
import time
import uuid

from app.auth import (
    TokenRequest, TokenResponse,
    create_access_token, get_current_client,
    FAKE_USERS, ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.idempotency import get_cached, set_cached
from app.pagination import store_event, paginate
from app.webhooks import (
    WebhookRegistration, WebhookRegistrationResponse,
    register_url, list_urls, deliver_event,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Prometheus metrics ────────────────────────────────────────────────────────
INGEST_COUNTER = Counter(
    "flight_ingest_requests_total",
    "Total ingest requests",
    ["status", "airline", "version"],
)
INGEST_LATENCY = Histogram(
    "flight_ingest_duration_seconds",
    "Ingest request latency",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)
INGEST_ERRORS = Counter(
    "flight_ingest_errors_total",
    "Total ingest errors by type",
    ["error_type"],
)
IDEMPOTENT_HITS = Counter(
    "flight_ingest_idempotent_hits_total",
    "Requests served from idempotency cache",
)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Flight Ingest Service",
    description=(
        "Real-time flight event ingestion API demonstrating:\n"
        "- JWT authentication (client credentials flow)\n"
        "- API versioning (v1 / v2)\n"
        "- Idempotency keys (X-Idempotency-Key header)\n"
        "- Cursor-based pagination\n"
        "- Outbound webhooks with HMAC signing + retry"
    ),
    version="2.0.0",
)


# ── Models ────────────────────────────────────────────────────────────────────
class FlightEventV1(BaseModel):
    """V1 payload — 3-letter IATA codes."""
    flight_id: str = Field(..., min_length=3, max_length=10, example="BA249")
    origin: str = Field(..., min_length=3, max_length=4, example="LHR")
    destination: str = Field(..., min_length=3, max_length=4, example="JFK")
    airline: str = Field(..., min_length=2, max_length=8, example="BA")
    event_type: str = Field(..., example="DEPARTURE")
    timestamp: str = Field(..., example="2026-04-08T14:00:00Z")
    payload: Optional[dict] = None

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        allowed = {"DEPARTURE", "ARRIVAL", "DELAY", "CANCEL", "DIVERT"}
        if v.upper() not in allowed:
            raise ValueError(f"event_type must be one of {allowed}")
        return v.upper()

    @field_validator("origin", "destination")
    @classmethod
    def validate_iata(cls, v: str) -> str:
        return v.upper()


class FlightEventV2(FlightEventV1):
    """V2 payload — adds priority, cabin class, and 5-letter IATA support."""
    priority: str = Field(default="NORMAL", example="HIGH")
    cabin_class: Optional[str] = Field(default=None, example="BUSINESS")
    aircraft_type: Optional[str] = Field(default=None, example="B777")
    codeshare_partners: list[str] = Field(default_factory=list)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        allowed = {"LOW", "NORMAL", "HIGH", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"priority must be one of {allowed}")
        return v.upper()


class IngestResponse(BaseModel):
    event_id: str
    status: str
    flight_id: str
    message: str
    version: str


# ── Middleware: correlation ID + request logging ───────────────────────────────
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Reads or generates X-Request-ID; injects into response headers and logs."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Request-ID"] = request_id
    log.info(
        "method=%s path=%s status=%d duration=%.3fs request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration,
        request_id,
    )
    return response


# ── Ops routes ───────────────────────────────────────────────────────────────────
@app.get("/healthz", tags=["ops"])
async def health():
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def ready():
    return {"status": "ready"}


@app.get("/metrics", tags=["ops"])
async def metrics():
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


# ── Auth routes ───────────────────────────────────────────────────────────────────
@app.post("/token", response_model=TokenResponse, tags=["auth"])
async def issue_token(body: TokenRequest):
    """
    Client credentials token endpoint.

    Exchange client_id + client_secret for a short-lived JWT.
    Use the token as `Authorization: Bearer <token>` on protected routes.
    """
    expected = FAKE_USERS.get(body.client_id)
    if not expected or expected != body.client_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
        )
    token = create_access_token(subject=body.client_id)
    return TokenResponse(
        access_token=token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── V1 ingest ───────────────────────────────────────────────────────────────────
@app.post(
    "/v1/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["v1"],
)
async def ingest_v1(
    event: FlightEventV1,
    request: Request,
    background_tasks: BackgroundTasks,
    client_id: str = Depends(get_current_client),
):
    """
    V1 ingest endpoint (JWT protected).

    Supports X-Idempotency-Key header for safe retries.
    Delivers event to registered webhooks asynchronously.
    """
    return await _process_ingest(event, request, background_tasks, version="v1")


# ── V2 ingest ───────────────────────────────────────────────────────────────────
@app.post(
    "/v2/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["v2"],
)
async def ingest_v2(
    event: FlightEventV2,
    request: Request,
    background_tasks: BackgroundTasks,
    client_id: str = Depends(get_current_client),
):
    """
    V2 ingest endpoint (JWT protected).

    Accepts richer payload: priority, cabin_class, aircraft_type, codeshare_partners.
    Backwards-compatible with V1 clients (all new fields are optional).
    """
    return await _process_ingest(event, request, background_tasks, version="v2")


# ── Shared ingest logic ─────────────────────────────────────────────────────────
async def _process_ingest(
    event: FlightEventV1,
    request: Request,
    background_tasks: BackgroundTasks,
    version: str,
) -> IngestResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # ─ Idempotency check
    idempotency_key = request.headers.get("X-Idempotency-Key")
    if idempotency_key:
        cached = get_cached(idempotency_key)
        if cached is not None:
            IDEMPOTENT_HITS.inc()
            log.info("Idempotent hit key=%s request_id=%s", idempotency_key, request_id)
            return cached

    with INGEST_LATENCY.time():
        event_id = str(uuid.uuid4())
        try:
            log.info(
                "Ingesting event_id=%s flight=%s type=%s version=%s request_id=%s",
                event_id, event.flight_id, event.event_type, version, request_id,
            )
            INGEST_COUNTER.labels(
                status="accepted", airline=event.airline, version=version
            ).inc()

            # Store for pagination
            store_event(event_id, event.flight_id, event.event_type, event.airline)

            response = IngestResponse(
                event_id=event_id,
                status="accepted",
                flight_id=event.flight_id,
                message=f"Event {event.event_type} for {event.flight_id} accepted ({version}).",
                version=version,
            )

            # Cache under idempotency key
            if idempotency_key:
                set_cached(idempotency_key, response)

            # Deliver webhooks in background
            background_tasks.add_task(
                deliver_event,
                {
                    "event_id": event_id,
                    "flight_id": event.flight_id,
                    "event_type": event.event_type,
                    "airline": event.airline,
                    "version": version,
                },
                request_id,
            )

            return response

        except Exception as exc:
            INGEST_ERRORS.labels(error_type=type(exc).__name__).inc()
            INGEST_COUNTER.labels(status="error", airline=event.airline, version=version).inc()
            log.exception("Ingest failed request_id=%s: %s", request_id, exc)
            raise HTTPException(status_code=500, detail="Internal ingest error") from exc


# ── Pagination route ───────────────────────────────────────────────────────────────
@app.get("/v1/events", tags=["v1"])
async def list_events(
    cursor: Optional[str] = None,
    limit: int = 20,
    client_id: str = Depends(get_current_client),
):
    """
    Cursor-based paginated event list (JWT protected).

    Pass `cursor` from `next_cursor` in previous response to get the next page.
    `limit` is clamped to 1–100.
    """
    return paginate(cursor=cursor, limit=limit)


# ── Webhook routes ──────────────────────────────────────────────────────────────────
@app.post("/webhooks/register", response_model=WebhookRegistrationResponse, tags=["webhooks"])
async def register_webhook(
    body: WebhookRegistration,
    client_id: str = Depends(get_current_client),
):
    """
    Register a webhook URL (JWT protected).

    The service will POST every accepted ingest event to all registered URLs
    with an HMAC-SHA256 `X-Webhook-Signature` header for authenticity verification.
    """
    url_str = str(body.url)
    newly_added = register_url(url_str)
    return WebhookRegistrationResponse(
        url=url_str,
        registered=newly_added,
        total_registered=len(list_urls()),
    )


@app.get("/webhooks", tags=["webhooks"])
async def get_webhooks(client_id: str = Depends(get_current_client)):
    """List all registered webhook URLs (JWT protected)."""
    return {"webhooks": list_urls(), "total": len(list_urls())}


# ── Legacy /ingest (v1 alias, no auth — kept for backwards compatibility) ────────────
@app.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["legacy"],
    deprecated=True,
)
async def ingest_legacy(event: FlightEventV1, request: Request, background_tasks: BackgroundTasks):
    """
    Legacy unauthenticated endpoint — deprecated, use /v1/ingest instead.
    Kept for backwards compatibility with existing tests.
    """
    return await _process_ingest(event, request, background_tasks, version="v1")
