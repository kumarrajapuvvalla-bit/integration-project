"""Tests for JWT authentication: /token endpoint and protected routes."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _get_token(client_id="ops-service", secret="secret123") -> str:
    r = client.post("/token", json={"client_id": client_id, "client_secret": secret})
    assert r.status_code == 200, f"Token request failed: {r.text}"
    return r.json()["access_token"]


class TestAuth:
    def test_token_issued_for_valid_credentials(self):
        r = client.post("/token", json={"client_id": "ops-service", "client_secret": "secret123"})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

    def test_token_rejected_for_wrong_secret(self):
        r = client.post("/token", json={"client_id": "ops-service", "client_secret": "wrong"})
        assert r.status_code == 401

    def test_token_rejected_for_unknown_client(self):
        r = client.post("/token", json={"client_id": "ghost", "client_secret": "any"})
        assert r.status_code == 401

    def test_protected_route_requires_auth(self):
        r = client.post("/v1/ingest", json={
            "flight_id": "BA100", "origin": "LHR", "destination": "JFK",
            "airline": "BA", "event_type": "DEPARTURE", "timestamp": "2026-01-01T00:00:00Z",
        })
        assert r.status_code == 403  # no auth header

    def test_protected_route_rejects_invalid_token(self):
        r = client.post("/v1/ingest",
            json={"flight_id": "BA100", "origin": "LHR", "destination": "JFK",
                  "airline": "BA", "event_type": "DEPARTURE", "timestamp": "2026-01-01T00:00:00Z"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert r.status_code == 401

    def test_protected_route_accepts_valid_token(self):
        token = _get_token()
        r = client.post("/v1/ingest",
            json={"flight_id": "BA100", "origin": "LHR", "destination": "JFK",
                  "airline": "BA", "event_type": "DEPARTURE", "timestamp": "2026-01-01T00:00:00Z"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 202
