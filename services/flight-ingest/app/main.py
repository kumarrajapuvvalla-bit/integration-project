from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import logging
import time
import uuid

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Prometheus metrics ────────────────────────────────────────────────────────
INGEST_COUNTER = Counter(
    "flight_ingest_requests_total",
    "Total ingest requests",
    ["status", "airline"],
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

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Flight Ingest Service",
    description="Receives real-time flight event payloads and validates them for downstream processing.",
    version="1.0.0",
)


# ── Models ────────────────────────────────────────────────────────────────────
class FlightEvent(BaseModel):
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


class IngestResponse(BaseModel):
    event_id: str
    status: str
    flight_id: str
    message: str


# ── Middleware: request logging ───────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    log.info(
        "method=%s path=%s status=%d duration=%.3fs",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )
    return response


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/healthz", tags=["ops"])
async def health():
    """Kubernetes liveness probe."""
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def ready():
    """Kubernetes readiness probe."""
    return {"status": "ready"}


@app.get("/metrics", tags=["ops"])
async def metrics():
    """Prometheus metrics endpoint."""
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["ingest"],
)
async def ingest_event(event: FlightEvent):
    """
    Ingest a flight event payload.

    Validates the payload, assigns a tracking ID, and emits Prometheus metrics.
    In production this would publish to Kafka / SQS.
    """
    with INGEST_LATENCY.time():
        event_id = str(uuid.uuid4())
        try:
            log.info(
                "Ingesting event event_id=%s flight=%s type=%s",
                event_id,
                event.flight_id,
                event.event_type,
            )
            INGEST_COUNTER.labels(status="accepted", airline=event.airline).inc()
            return IngestResponse(
                event_id=event_id,
                status="accepted",
                flight_id=event.flight_id,
                message=f"Event {event.event_type} for {event.flight_id} accepted.",
            )
        except Exception as exc:
            INGEST_ERRORS.labels(error_type=type(exc).__name__).inc()
            INGEST_COUNTER.labels(status="error", airline=event.airline).inc()
            log.exception("Ingest failed: %s", exc)
            raise HTTPException(status_code=500, detail="Internal ingest error") from exc


@app.get("/events/summary", tags=["ingest"])
async def events_summary():
    """Returns a summary of ingest counters."""
    return {
        "description": "See /metrics for full Prometheus counters.",
        "note": "In production this would query a Redis or TimescaleDB store.",
    }
