#!/usr/bin/env bash

# Send a Slack notification via Incoming Webhook.
# Usage: slack_notify.sh "message" "webhook_url"

set -euo pipefail

MESSAGE=${1:-"Build notification"}
WEBHOOK_URL=${2:?"You must provide a webhook URL"}

payload=$(cat <<EOF
{
  "text": "$MESSAGE",
  "mrkdwn": true
}
EOF
)

curl -X POST -H 'Content-type: application/json' --data "$payload" "$WEBHOOK_URL"
