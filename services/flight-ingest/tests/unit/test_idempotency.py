"""Tests for idempotency key behaviour."""
import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _token() -> str:
    r = client.post("/token", json={"client_id": "ops-service", "client_secret": "secret123"})
    return r.json()["access_token"]


PAYLOAD = {
    "flight_id": "BA999",
    "origin": "LHR",
    "destination": "CDG",
    "airline": "BA",
    "event_type": "DEPARTURE",
    "timestamp": "2026-04-01T08:00:00Z",
}


class TestIdempotency:
    def test_same_key_returns_same_event_id(self):
        token = _token()
        key = str(uuid.uuid4())
        headers = {"Authorization": f"Bearer {token}", "X-Idempotency-Key": key}
        r1 = client.post("/v1/ingest", json=PAYLOAD, headers=headers)
        r2 = client.post("/v1/ingest", json=PAYLOAD, headers=headers)
        assert r1.status_code == r2.status_code == 202
        assert r1.json()["event_id"] == r2.json()["event_id"]

    def test_different_keys_produce_different_event_ids(self):
        token = _token()
        h1 = {"Authorization": f"Bearer {token}", "X-Idempotency-Key": str(uuid.uuid4())}
        h2 = {"Authorization": f"Bearer {token}", "X-Idempotency-Key": str(uuid.uuid4())}
        r1 = client.post("/v1/ingest", json=PAYLOAD, headers=h1)
        r2 = client.post("/v1/ingest", json=PAYLOAD, headers=h2)
        assert r1.json()["event_id"] != r2.json()["event_id"]

    def test_no_key_always_creates_new_event(self):
        token = _token()
        headers = {"Authorization": f"Bearer {token}"}
        r1 = client.post("/v1/ingest", json=PAYLOAD, headers=headers)
        r2 = client.post("/v1/ingest", json=PAYLOAD, headers=headers)
        # Without idempotency key, two separate event_ids are generated
        assert r1.json()["event_id"] != r2.json()["event_id"]
