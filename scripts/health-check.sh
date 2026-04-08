#!/usr/bin/env bash
# health-check.sh — polls a Kubernetes deployment until all pods are Ready
# Usage: ./scripts/health-check.sh <release-name> <namespace> [timeout-seconds]
set -euo pipefail

RELEASE="${1:-flight-ingest}"
NAMESPACE="${2:-integrations}"
TIMEOUT="${3:-120}"
INTERVAL=5
elapsed=0

echo "[health-check] Waiting for ${RELEASE} in ${NAMESPACE} (timeout ${TIMEOUT}s)..."

while true; do
    READY=$(kubectl get deployment "${RELEASE}" \
        -n "${NAMESPACE}" \
        -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    DESIRED=$(kubectl get deployment "${RELEASE}" \
        -n "${NAMESPACE}" \
        -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")

    echo "[health-check] ${READY}/${DESIRED} pods ready (${elapsed}s elapsed)"

    if [[ "${READY}" == "${DESIRED}" && "${DESIRED}" != "0" ]]; then
        echo "[health-check] ✅ ${RELEASE} is healthy."
        exit 0
    fi

    if [[ ${elapsed} -ge ${TIMEOUT} ]]; then
        echo "[health-check] ❌ Timed out waiting for ${RELEASE} to become healthy."
        kubectl describe deployment "${RELEASE}" -n "${NAMESPACE}" || true
        kubectl get pods -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE}" || true
        exit 1
    fi

    sleep "${INTERVAL}"
    elapsed=$((elapsed + INTERVAL))
done
