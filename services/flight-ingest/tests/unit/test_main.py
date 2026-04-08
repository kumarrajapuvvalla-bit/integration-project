import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── Health endpoints ──────────────────────────────────────────────────────────
class TestHealth:
    def test_liveness(self):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_readiness(self):
        r = client.get("/readyz")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"

    def test_metrics_endpoint(self):
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "flight_ingest_requests_total" in r.text


# ── Ingest endpoint ───────────────────────────────────────────────────────────
class TestIngest:
    VALID_PAYLOAD = {
        "flight_id": "BA249",
        "origin": "LHR",
        "destination": "JFK",
        "airline": "BA",
        "event_type": "DEPARTURE",
        "timestamp": "2026-04-08T14:00:00Z",
    }

    def test_valid_departure(self):
        r = client.post("/ingest", json=self.VALID_PAYLOAD)
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "accepted"
        assert body["flight_id"] == "BA249"
        assert "event_id" in body

    def test_valid_arrival(self):
        payload = {**self.VALID_PAYLOAD, "event_type": "ARRIVAL"}
        r = client.post("/ingest", json=payload)
        assert r.status_code == 202

    def test_invalid_event_type(self):
        payload = {**self.VALID_PAYLOAD, "event_type": "UNKNOWN"}
        r = client.post("/ingest", json=payload)
        assert r.status_code == 422

    def test_missing_required_field(self):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != "flight_id"}
        r = client.post("/ingest", json=payload)
        assert r.status_code == 422

    def test_origin_uppercased(self):
        payload = {**self.VALID_PAYLOAD, "origin": "lhr"}
        r = client.post("/ingest", json=payload)
        assert r.status_code == 202

    def test_event_id_is_uuid(self):
        import uuid
        r = client.post("/ingest", json=self.VALID_PAYLOAD)
        body = r.json()
        uuid.UUID(body["event_id"])  # raises if not valid UUID

    def test_cancel_event(self):
        payload = {**self.VALID_PAYLOAD, "event_type": "CANCEL"}
        r = client.post("/ingest", json=payload)
        assert r.status_code == 202

    def test_divert_event(self):
        payload = {**self.VALID_PAYLOAD, "event_type": "DIVERT"}
        r = client.post("/ingest", json=payload)
        assert r.status_code == 202

    def test_delay_with_payload(self):
        payload = {
            **self.VALID_PAYLOAD,
            "event_type": "DELAY",
            "payload": {"delay_minutes": 45, "reason": "ATC"},
        }
        r = client.post("/ingest", json=payload)
        assert r.status_code == 202
