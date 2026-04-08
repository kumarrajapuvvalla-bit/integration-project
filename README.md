# Integration Project

[![Rust CI](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/rust-ci.yml/badge.svg)](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/rust-ci.yml)
[![Python CI](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/python-ci.yml/badge.svg)](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/python-ci.yml)
[![Integration Tests](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/kumarrajapuvvalla-bit/integration-project/actions/workflows/integration-tests.yml)

A **production-grade multi-language CI/CD platform** demonstrating how a real DevOps team integrates Python, Rust, Docker, Helm, Jenkins, and GitHub Actions into a single cohesive pipeline.

The story: a flight operations team needs a reliable event ingest pipeline with automated quality gates, security scanning at every layer, and zero-downtime Kubernetes deployments.

---

## What’s in here

```
├── Jenkinsfile                    # 10-stage declarative pipeline
├── .github/workflows/
│   ├── python-ci.yml              # Python lint + test + Docker smoke (3.11 & 3.12)
│   ├── rust-ci.yml                # Rust build + clippy + audit (stable & beta)
│   └── integration-tests.yml      # End-to-end tests (daily + on-push)
├── services/
│   └── flight-ingest/             # FastAPI microservice
│       ├── app/main.py            # /ingest, /healthz, /readyz, /metrics
│       ├── tests/unit/            # 9 pytest unit tests
│       ├── tests/integration/     # Full end-to-end tests
│       ├── Dockerfile             # Multi-stage, non-root, CIS hardened
│       └── requirements.txt
├── tools/
│   └── log-parser/                # Rust CLI: parses Jenkins logs → structured JSON
├── helm/
│   └── flight-ingest/             # Helm chart with HPA, PDB, ServiceMonitor
├── scripts/
│   ├── trivy-scan.sh              # Filesystem + image CVE scanning
│   ├── health-check.sh            # Post-deploy readiness polling
│   ├── rollback.sh                # Helm rollback with health verification
│   └── slack_notify.sh            # Rich Slack build notifications
└── docs/
    └── ARCHITECTURE.md            # Mermaid pipeline + sequence diagrams
```

---

## Jenkins Pipeline (10 stages)

| Stage | What happens |
|-------|--------------|
| 1. Checkout | Fetch source, capture author + commit msg |
| 2. Lint | Python (ruff + bandit) + Rust (clippy + fmt) + Helm lint — **parallel** |
| 3. Build | Python compile + Rust release build — **parallel** |
| 4. Test | Pytest with JUnit + coverage + cargo test — **parallel** |
| 5. SonarQube | Multi-language code quality analysis |
| 6. Quality Gate | Abort pipeline if SonarQube gate fails |
| 7. Security | OWASP safety + Trivy FS + cargo-audit — **parallel** |
| 8. Docker | Build multi-stage image, push to GHCR, Trivy image scan |
| 9. Staging | `helm upgrade --install`, health-check polling, Slack notify |
| 10. Production | Manual approval gate (ops-team), prod Helm deploy |

---

## Quick Start

### Run the Python service locally

```bash
cd services/flight-ingest
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# Test it
curl -X POST http://localhost:8080/ingest \
  -H 'Content-Type: application/json' \
  -d '{"flight_id": "BA249", "origin": "LHR", "destination": "JFK", \
       "airline": "BA", "event_type": "DEPARTURE", "timestamp": "2026-04-08T14:00:00Z"}'

# View Prometheus metrics
curl http://localhost:8080/metrics
```

### Run the Rust log-parser

```bash
cd tools/log-parser
cargo build --release

# Parse a Jenkins log
cat my-build.log | ./target/release/log-parser --stdin --format json

# Or from a file with exit code on failure
./target/release/log-parser --input build.log --fail-on-error
```

### Run all tests

```bash
# Python unit tests
cd services/flight-ingest
pip install pytest pytest-cov httpx
pytest tests/unit/ -v --cov=app

# Rust tests
cd tools/log-parser
cargo test --all
```

---

## Event Types

The `/ingest` endpoint accepts the following `event_type` values:

| Event | Meaning |
|-------|---------|
| `DEPARTURE` | Aircraft departed origin |
| `ARRIVAL` | Aircraft arrived at destination |
| `DELAY` | Flight delayed (include `payload.delay_minutes`) |
| `CANCEL` | Flight cancelled |
| `DIVERT` | Flight diverted to alternate airport |

---

## Security

- **Trivy** scans both the filesystem and Docker image for CVEs
- **OWASP safety** checks Python dependencies against known vulnerability databases
- **cargo-audit** scans Rust dependencies against the RustSec Advisory DB
- **Bandit** checks Python source for common security antipatterns
- **Docker image** runs as non-root (UID 1000), read-only root filesystem, all capabilities dropped
- **SonarQube** enforces quality + security hotspot gates before any deployment

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full Mermaid pipeline and sequence diagrams.

---

*Part of [kumarrajapuvvalla-bit](https://github.com/kumarrajapuvvalla-bit)’s DevOps portfolio. For educational and portfolio purposes.*
