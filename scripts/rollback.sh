#!/usr/bin/env bash
# rollback.sh — rolls back a Helm release to the previous revision
# Usage: ./scripts/rollback.sh <release-name> <namespace> [revision]
set -euo pipefail

RELEASE="${1:-flight-ingest}"
NAMESPACE="${2:-integrations}"
REVISION="${3:-0}"  # 0 = previous

echo "[rollback] Rolling back ${RELEASE} in ${NAMESPACE} to revision ${REVISION}..."
helm rollback "${RELEASE}" "${REVISION}" \
    --namespace "${NAMESPACE}" \
    --wait \
    --timeout 5m

echo "[rollback] Verifying deployment health post-rollback..."
./scripts/health-check.sh "${RELEASE}" "${NAMESPACE}"

echo "[rollback] ✅ Rollback complete."
