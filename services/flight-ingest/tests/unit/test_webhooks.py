"""Tests for webhook registration."""
import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _token() -> str:
    r = client.post("/token", json={"client_id": "ops-service", "client_secret": "secret123"})
    return r.json()["access_token"]


class TestWebhooks:
    def test_register_webhook(self):
        token = _token()
        r = client.post("/webhooks/register",
            json={"url": "https://example.com/hook", "description": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["registered"] is True or body["total_registered"] >= 1

    def test_duplicate_webhook_not_registered_twice(self):
        token = _token()
        url = f"https://example.com/hook-{uuid.uuid4()}"
        r1 = client.post("/webhooks/register",
            json={"url": url}, headers={"Authorization": f"Bearer {token}"})
        r2 = client.post("/webhooks/register",
            json={"url": url}, headers={"Authorization": f"Bearer {token}"})
        assert r1.json()["registered"] is True
        assert r2.json()["registered"] is False

    def test_list_webhooks(self):
        token = _token()
        r = client.get("/webhooks", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert "webhooks" in r.json()

    def test_webhooks_require_auth(self):
        r = client.post("/webhooks/register", json={"url": "https://example.com/hook"})
        assert r.status_code == 403
