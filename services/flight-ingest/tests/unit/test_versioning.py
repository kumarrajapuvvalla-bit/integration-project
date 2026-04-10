"""Tests for API versioning: /v1/ingest vs /v2/ingest."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _token() -> str:
    r = client.post("/token", json={"client_id": "ops-service", "client_secret": "secret123"})
    return r.json()["access_token"]


BASE_PAYLOAD = {
    "flight_id": "EK007",
    "origin": "DXB",
    "destination": "LHR",
    "airline": "EK",
    "event_type": "DEPARTURE",
    "timestamp": "2026-04-01T10:00:00Z",
}


class TestVersioning:
    def test_v1_accepts_minimal_payload(self):
        token = _token()
        r = client.post("/v1/ingest", json=BASE_PAYLOAD,
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 202
        assert r.json()["version"] == "v1"

    def test_v2_accepts_richer_payload(self):
        token = _token()
        payload = {**BASE_PAYLOAD, "priority": "HIGH", "cabin_class": "BUSINESS",
                   "aircraft_type": "B777", "codeshare_partners": ["QF", "BA"]}
        r = client.post("/v2/ingest", json=payload,
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 202
        assert r.json()["version"] == "v2"

    def test_v2_rejects_invalid_priority(self):
        token = _token()
        payload = {**BASE_PAYLOAD, "priority": "MEGA"}
        r = client.post("/v2/ingest", json=payload,
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422

    def test_v2_defaults_priority_to_normal(self):
        token = _token()
        r = client.post("/v2/ingest", json=BASE_PAYLOAD,
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 202

    def test_legacy_ingest_still_works(self):
        """Legacy /ingest (no auth) must remain backwards-compatible."""
        r = client.post("/ingest", json=BASE_PAYLOAD)
        assert r.status_code == 202

    def test_response_includes_version_field(self):
        token = _token()
        r = client.post("/v1/ingest", json=BASE_PAYLOAD,
                        headers={"Authorization": f"Bearer {token}"})
        assert "version" in r.json()
