#!/bin/sh
# local-stack.sh — Manage the local Elastic development stack
# Wraps the upstream elastic-start-local scripts with extra services (APM server)
# and utility operations (start, stop, status).
#
# Usage:
#   ./local-stack.sh -o start   # Start the full stack
#   ./local-stack.sh -o stop    # Stop the full stack
#   ./local-stack.sh -o status  # Show container status
#   ./local-stack.sh -o destroy # Tear down stack and delete all data
#   ./local-stack.sh -h         # Show this help

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ELASTIC_DIR="${SCRIPT_DIR}/elastic-start-local"

# -----------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") -o <operation> [options]

Manage the local Elastic development stack (Elasticsearch, Kibana, APM server).

Options:
  -o, --operation <value>  Operation to perform. Required.
                           Values: start | stop | status | destroy
  -h, --help               Show this help message and exit

Operations:
  start   Validate/refresh the API key, enforce the Basic license, then
          bring up Elasticsearch, Kibana and the APM server.
  stop    Stop all stack services (Elasticsearch, Kibana, APM server).
  status  Show the running status of all stack containers.
  destroy Stop and remove all stack containers and volumes (deletes all data).

Examples:
  $(basename "$0") -o start
  $(basename "$0") --operation stop
  $(basename "$0") -o status
EOF
}

# -----------------------------------------------------------------------
# Argument parsing
# -----------------------------------------------------------------------
operation=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -o|--operation)
      if [ "$#" -lt 2 ]; then
        echo "Error: -o/--operation requires a value (start|stop|status)" >&2
        exit 1
      fi
      operation="$2"
      shift 2
      ;;
    *)
      echo "Error: Unknown argument '$1'" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [ -z "$operation" ]; then
  usage
  exit 0
fi

case "$operation" in
  start|stop|status|destroy) ;;
  *)
    echo "Error: Invalid operation '$operation'. Use start, stop, or status." >&2
    exit 1
    ;;
esac

# -----------------------------------------------------------------------
# Operations
# -----------------------------------------------------------------------

# Seed .env on a fresh clone. The upstream start.sh and every operation below
# source ./.env ("./.env: No such file or directory" otherwise), but only the
# non-secret .env.example is tracked (.env is gitignored). Copy the template when
# .env is absent so a clean checkout works for ALL operations; an existing .env is
# left untouched. Assumes the working directory is already ELASTIC_DIR.
seed_env() {
  if [ ! -f ./.env ]; then
    echo "No .env found -- seeding from .env.example (fresh clone)."
    cp ./.env.example ./.env || { echo "Error: failed to seed .env from .env.example" >&2; exit 1; }
  fi
}

do_start() {
  cd "${ELASTIC_DIR}"

  # Step 0: Seed .env on a fresh clone (see seed_env) so upstream start.sh can
  # source it instead of dying on a missing ./.env.
  seed_env

  # Step 1: Upstream start.sh (disk check, trial-expiry, full stack up)
  ./start.sh

  # Step 2: Reload .env + .env.local (start.sh may have updated .env)
  . ./.env
  [ -f ./.env.local ] && . ./.env.local

  # Step 3: Verify API key; regenerate if stale (fresh clone, containers deleted, etc.)
  echo "---------------------------------------------------------------------"
  echo "Checking Elasticsearch API key..."
  echo "---------------------------------------------------------------------"
  api_check=$(curl -s -X GET "${ES_LOCAL_URL}/_security/_authenticate" \
    -H "Authorization: ApiKey ${ES_LOCAL_API_KEY:-}" \
    -o /dev/null -w '%{http_code}\n')

  if [ "$api_check" != "200" ]; then
    echo "API key is invalid or missing. Generating a new one..."
    new_api_key_json=$(curl -s -X POST "${ES_LOCAL_URL}/_security/api_key" \
      -u "elastic:${ES_LOCAL_PASSWORD}" \
      -H "Content-Type: application/json" \
      -d '{"name": "start-local"}')
    new_api_key=$(echo "$new_api_key_json" | \
      python3 -c "import sys,json; print(json.load(sys.stdin).get('encoded',''))" \
      2>/dev/null || echo "")

    if [ -n "$new_api_key" ]; then
      echo "ES_LOCAL_API_KEY=$new_api_key" > .env.local
      export ES_LOCAL_API_KEY="$new_api_key"
      echo "✅ API key written to .env.local"
    else
      echo "Warning: Could not generate a new API key." >&2
    fi
  else
    echo "✅ API key is valid"
  fi
  echo

  # Step 4: Enforce Basic license (not handled by upstream when already set to basic)
  . ./.env
  [ -f ./.env.local ] && . ./.env.local
  if [ "${ES_LOCAL_LICENSE:-}" = "basic" ]; then
    echo "---------------------------------------------------------------------"
    echo "Ensuring Basic license..."
    echo "---------------------------------------------------------------------"
    result=$(curl -s -X POST "${ES_LOCAL_URL}/_license/start_basic?acknowledge=true" \
      -H "Authorization: ApiKey ${ES_LOCAL_API_KEY}" \
      -o /dev/null -w '%{http_code}\n')
    if [ "$result" = "200" ] || [ "$result" = "403" ]; then
      echo "✅ Basic license ensured"
    else
      echo "Error: Cannot update the license (HTTP $result)" >&2
      exit 1
    fi
    echo
  fi

  # Step 5: Start APM server (project addition on top of upstream stack)
  echo "---------------------------------------------------------------------"
  echo "Starting APM server..."
  echo "---------------------------------------------------------------------"
  docker compose \
    -f docker-compose.yml \
    -f docker-compose.apm.yml \
    up --wait apm-server
  echo "✅ APM server started"
}

do_stop() {
  cd "${ELASTIC_DIR}"
  seed_env
  . ./.env

  echo "---------------------------------------------------------------------"
  echo "Stopping APM server..."
  echo "---------------------------------------------------------------------"
  docker compose \
    -f docker-compose.yml \
    -f docker-compose.apm.yml \
    stop apm-server

  echo
  echo "---------------------------------------------------------------------"
  echo "Stopping Elasticsearch, Kibana and remaining services..."
  echo "---------------------------------------------------------------------"
  docker compose stop

  echo
  echo "✅ Stack stopped"
}

do_status() {
  cd "${ELASTIC_DIR}"
  seed_env
  . ./.env

  echo "---------------------------------------------------------------------"
  echo "Local Elastic Stack — container status"
  echo "---------------------------------------------------------------------"
  docker compose \
    -f docker-compose.yml \
    -f docker-compose.apm.yml \
    ps
}

do_destroy() {
  cd "${ELASTIC_DIR}"
  seed_env
  . ./.env

  echo "---------------------------------------------------------------------"
  echo "Destroying Elastic Stack (containers, networks, and volumes)..."
  echo "---------------------------------------------------------------------"
  docker compose \
    -f docker-compose.yml \
    -f docker-compose.apm.yml \
    down --volumes --remove-orphans

  # Remove generated local env so the next start creates fresh credentials
  rm -f .env.local

  echo
  echo "✅ Stack destroyed — all data removed. Run 'make stack-start' for a fresh stack."
}

# -----------------------------------------------------------------------
# Dispatch
# -----------------------------------------------------------------------
case "$operation" in
  start)   do_start   ;;
  stop)    do_stop    ;;
  status)  do_status  ;;
  destroy) do_destroy ;;
esac
