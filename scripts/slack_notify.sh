#!/usr/bin/env bash
# slack_notify.sh — posts a rich Slack message via Incoming Webhook
# Usage: ./scripts/slack_notify.sh "<message>" "<webhook-url>"
set -euo pipefail

MESSAGE="${1:?Usage: slack_notify.sh <message> <webhook-url>}"
WEBHOOK_URL="${2:?Usage: slack_notify.sh <message> <webhook-url>}"

# Build JSON payload using printf to handle special characters
PAYLOAD=$(printf '{"text": "%s"}' "$(echo "$MESSAGE" | sed 's/"/\\"/g')")

curl --silent --fail --show-error \
    -X POST \
    -H 'Content-Type: application/json' \
    --data "${PAYLOAD}" \
    "${WEBHOOK_URL}"

echo ""
echo "[slack_notify] Message sent."
