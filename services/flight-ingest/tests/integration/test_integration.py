import pytest
import httpx
import os

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        yield c


class TestIntegrationHealth:
    def test_liveness_probe(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_readiness_probe(self, client):
        r = client.get("/readyz")
        assert r.status_code == 200

    def test_metrics_contains_counters(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "flight_ingest" in r.text


class TestIntegrationIngest:
    def test_full_departure_roundtrip(self, client):
        """Full end-to-end: post event and verify counter increments in /metrics."""
        payload = {
            "flight_id": "EK007",
            "origin": "DXB",
            "destination": "LHR",
            "airline": "EK",
            "event_type": "DEPARTURE",
            "timestamp": "2026-04-08T18:00:00Z",
        }
        r = client.post("/ingest", json=payload)
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "accepted"
        assert body["flight_id"] == "EK007"

        # Verify counter incremented
        metrics = client.get("/metrics").text
        assert 'airline="EK"' in metrics

    def test_high_volume_ingest(self, client):
        """Simulate 20 sequential events — all should be accepted."""
        for i in range(20):
            r = client.post("/ingest", json={
                "flight_id": f"BA{100+i}",
                "origin": "LHR",
                "destination": "JFK",
                "airline": "BA",
                "event_type": "DEPARTURE",
                "timestamp": "2026-04-08T12:00:00Z",
            })
            assert r.status_code == 202, f"Failed on event {i}: {r.text}"
