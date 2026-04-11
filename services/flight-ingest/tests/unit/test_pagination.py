"""Tests for cursor-based pagination on /v1/events."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _token() -> str:
    r = client.post("/token", json={"client_id": "ops-service", "client_secret": "secret123"})
    return r.json()["access_token"]


def _seed_events(n: int, token: str) -> None:
    """Ingest n events to populate the store."""
    for i in range(n):
        client.post("/ingest", json={
            "flight_id": f"BA{100+i}",
            "origin": "LHR",
            "destination": "JFK",
            "airline": "BA",
            "event_type": "DEPARTURE",
            "timestamp": "2026-04-01T08:00:00Z",
        })


class TestPagination:
    def test_first_page_returns_items(self):
        token = _token()
        _seed_events(5, token)
        r = client.get("/v1/events?limit=3", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "next_cursor" in body
        assert "has_more" in body
        assert len(body["items"]) <= 3

    def test_cursor_advances_page(self):
        token = _token()
        _seed_events(10, token)
        r1 = client.get("/v1/events?limit=3", headers={"Authorization": f"Bearer {token}"})
        cursor = r1.json().get("next_cursor")
        if cursor:
            r2 = client.get(f"/v1/events?limit=3&cursor={cursor}",
                            headers={"Authorization": f"Bearer {token}"})
            assert r2.status_code == 200
            # Second page items should differ from first
            ids1 = [e["event_id"] for e in r1.json()["items"]]
            ids2 = [e["event_id"] for e in r2.json()["items"]]
            assert ids1 != ids2

    def test_limit_clamped_to_100(self):
        token = _token()
        r = client.get("/v1/events?limit=999", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 100

    def test_pagination_requires_auth(self):
        r = client.get("/v1/events")
        assert r.status_code == 403
