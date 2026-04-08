# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

WORKDIR /app

# Install deps in a separate layer for cache efficiency
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/kumarrajapuvvalla-bit/integration-project"
LABEL org.opencontainers.image.description="Flight Ingest Service"

# Non-root user (CIS hardening)
RUN useradd --create-home --shell /bin/bash appuser
USER appuser
WORKDIR /home/appuser

COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/app ./app

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
