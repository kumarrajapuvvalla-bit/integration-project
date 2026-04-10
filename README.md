# Integration Project

[![Rust CI](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/rust-ci.yml/badge.svg)](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/rust-ci.yml)
[![Python CI](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/python-ci.yml/badge.svg)](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/python-ci.yml)
[![Integration Tests](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/integration-tests.yml)

A **production-grade multi-language CI/CD platform** demonstrating advanced API engineering, DevSecOps, and platform engineering practices across Python, Rust, Docker, Helm, Jenkins, and GitHub Actions.

---

## Advanced API Features

### 1. JWT Authentication (Client Credentials Flow)
```bash
# Get a token
curl -X POST http://localhost:8080/token \
  -H 'Content-Type: application/json' \
  -d '{"client_id": "ops-service", "client_secret": "secret123"}'

# Use it
curl -X POST http://localhost:8080/v1/ingest \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"flight_id": "BA249", "origin": "LHR", "destination": "JFK", \
       "airline": "BA", "event_type": "DEPARTURE", "timestamp": "2026-04-10T10:00:00Z"}'
```

### 2. API Versioning (URI strategy)

| Endpoint | Version | Notes |
|----------|---------|-------|
| `POST /v1/ingest` | V1 | 3-letter IATA, standard fields |
| `POST /v2/ingest` | V2 | Adds `priority`, `cabin_class`, `aircraft_type`, `codeshare_partners` |
| `POST /ingest` | Legacy | Deprecated alias for v1, no auth required |

### 3. Idempotency Keys
```bash
# First call — event created
curl -X POST http://localhost:8080/v1/ingest \
  -H 'Authorization: Bearer <token>' \
  -H 'X-Idempotency-Key: my-unique-key-001' \
  -H 'Content-Type: application/json' \
  -d '{ ...payload... }'

# Second call with same key — returns identical response, event NOT duplicated
curl -X POST http://localhost:8080/v1/ingest \
  -H 'Authorization: Bearer <token>' \
  -H 'X-Idempotency-Key: my-unique-key-001' \
  -H 'Content-Type: application/json' \
  -d '{ ...payload... }'
```
Keys expire after 60 seconds. In production: Redis SETNX pattern.

### 4. Cursor-Based Pagination
```bash
# First page
curl 'http://localhost:8080/v1/events?limit=10' \
  -H 'Authorization: Bearer <token>'

# Next page (use next_cursor from previous response)
curl 'http://localhost:8080/v1/events?limit=10&cursor=<next_cursor>' \
  -H 'Authorization: Bearer <token>'
```
Cursors are opaque base64-encoded position indices. `limit` is clamped 1–100.

### 5. Outbound Webhooks with HMAC Signing
```bash
# Register your endpoint
curl -X POST http://localhost:8080/webhooks/register \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://your-server.com/events", "description": "prod listener"}'

# Every accepted ingest event is POSTed to your URL with:
# X-Webhook-Signature: sha256=<hmac>
# X-Request-ID: <correlation-id>
# Retries: 3 attempts with 2s/4s/8s exponential backoff
```

---

## Full API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/token` | — | Issue JWT (client credentials) |
| GET | `/healthz` | — | Liveness probe |
| GET | `/readyz` | — | Readiness probe |
| GET | `/metrics` | — | Prometheus scrape |
| POST | `/v1/ingest` | JWT | Ingest flight event (V1 payload) |
| POST | `/v2/ingest` | JWT | Ingest flight event (V2 payload) |
| GET | `/v1/events` | JWT | Paginated event list |
| POST | `/webhooks/register` | JWT | Register outbound webhook |
| GET | `/webhooks` | JWT | List registered webhooks |
| POST | `/ingest` | — | Legacy alias (deprecated) |

---

## Quick Start

```bash
cd services/flight-ingest
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# Interactive API docs
open http://localhost:8080/docs
```

---

## Repository Map

```
├── Jenkinsfile                    # 10-stage declarative pipeline
├── .github/workflows/
│   ├── python-ci.yml              # Python lint + test + Docker smoke
│   ├── rust-ci.yml                # Rust build + clippy + audit
│   └── integration-tests.yml      # End-to-end tests (daily + on-push)
├── services/
│   └── flight-ingest/
│       ├── app/
│       │   ├── main.py            # FastAPI app + all routes
│       │   ├── auth.py            # JWT token issuance + verification
│       │   ├── idempotency.py     # Idempotency key cache
│       │   ├── pagination.py      # Cursor-based event pagination
│       │   └── webhooks.py        # Outbound webhook delivery + HMAC signing
│       ├── tests/unit/
│       │   ├── test_auth.py       # JWT auth tests
│       │   ├── test_versioning.py # v1 vs v2 tests
│       │   ├── test_idempotency.py# Idempotency tests
│       │   ├── test_pagination.py # Cursor pagination tests
│       │   ├── test_webhooks.py   # Webhook registration tests
│       │   └── test_main.py       # Core endpoint tests
│       ├── Dockerfile
│       └── requirements.txt
├── tools/log-parser/              # Rust CLI: Jenkins log → structured JSON
├── helm/flight-ingest/            # Helm chart: HPA, PDB, ServiceMonitor
├── scripts/                       # trivy-scan, health-check, rollback, slack
└── docs/ARCHITECTURE.md           # Mermaid pipeline + sequence diagrams
```

---

*Part of [kumarrajapuvvalla-bit](https://github.com/kumarrajapuvvalla-bit)'s DevOps portfolio. For educational and portfolio purposes.*
