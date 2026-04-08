#!/usr/bin/env bash
# trivy-scan.sh — wraps Trivy with auto-install on CI runners
# Usage:
#   ./scripts/trivy-scan.sh fs .  --severity HIGH,CRITICAL
#   ./scripts/trivy-scan.sh image ghcr.io/myorg/myapp:tag --severity CRITICAL
set -euo pipefail

SCAN_TYPE="${1:-fs}"
TARGET="${2:-.}"
shift 2 || true
EXTRA_ARGS="$@"

if ! command -v trivy &>/dev/null; then
    echo "[trivy-scan] Trivy not found, installing..."
    curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
        | sh -s -- -b /usr/local/bin
fi

echo "[trivy-scan] Scanning ${SCAN_TYPE}: ${TARGET}"
trivy "${SCAN_TYPE}" \
    --no-progress \
    --format table \
    ${EXTRA_ARGS} \
    "${TARGET}"

echo "[trivy-scan] Done."
