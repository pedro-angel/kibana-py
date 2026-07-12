#!/usr/bin/env bash
# Provision the integration stack (Elasticsearch + Kibana + APM) and wait until
# all three are ready. Single source of truth for CI stack bring-up: called by
# BOTH the integration-probe workflow and the release integration gate, so the
# two can't drift.
#
# Assumes: repo checked out; Docker + Compose v2 on PATH (GitHub-hosted runners
# have them). Safe to run from any cwd.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
summary="${GITHUB_STEP_SUMMARY:-/dev/stderr}"

cd "$here/elastic-start-local"

# Non-secret dev env; the one template a fresh clone and CI both consume.
cp .env.example .env
# shellcheck disable=SC1091
set -a; . ./.env; set +a  # ES_LOCAL_PASSWORD etc. for the api-key mint below

# ES + Kibana (+ its one-shot kibana_settings) + the standalone APM server.
t0=$(date +%s)
docker compose -f docker-compose.yml -f docker-compose.apm.yml up --wait -d
echo "compose_up_seconds=$(( $(date +%s) - t0 ))" | tee -a "$summary"

# Kibana readiness: poll /api/status until "available". The compose 302
# healthcheck returns before plugins finish initializing (503 "not ready yet").
level=""
for _ in $(seq 1 60); do
  level="$(curl -s http://localhost:5601/api/status | jq -r '.status.overall.level // empty' 2>/dev/null || true)"
  [ "$level" = "available" ] && break
  sleep 5
done
[ "$level" = "available" ] || { echo "Kibana never reached 'available'" >&2; exit 1; }

# APM readiness: apm-server has no compose healthcheck, so poll its port.
code="000"
for _ in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8200 2>/dev/null || echo 000)"
  [ "$code" != "000" ] && break
  sleep 2
done
[ "$code" != "000" ] || { echo "APM server never answered on :8200" >&2; exit 1; }

echo "kibana=available apm_http=$code" | tee -a "$summary"

# Mint an ES API key so the api-key auth tests have a real key in CI. Locally
# this key lives in the untracked .env.local; CI has no such file. Written to
# $GITHUB_ENV so later steps -- and the integration conftest -- pick it up as
# ES_LOCAL_API_KEY (tests/integration/utils.py falls back to it).
if [ -n "${GITHUB_ENV:-}" ]; then
  api_key="$(curl -s -u "elastic:${ES_LOCAL_PASSWORD}" -X POST \
    "http://localhost:9200/_security/api_key" \
    -H 'Content-Type: application/json' -d '{"name":"kibana-py-ci"}' \
    | python3 -c "import sys, json; print(json.load(sys.stdin).get('encoded', ''))" 2>/dev/null || true)"
  if [ -n "$api_key" ]; then
    echo "ES_LOCAL_API_KEY=$api_key" >> "$GITHUB_ENV"
    echo "minted ES API key for api-key auth tests" | tee -a "$summary"
  else
    echo "WARNING: could not mint an ES API key (api-key tests may skip)" | tee -a "$summary"
  fi
fi
